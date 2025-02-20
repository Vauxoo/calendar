# Copyright 2021 Tecnativa - Jairo Llopis
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from random import random

from odoo import _, api, fields, models


class ResourceBookingType(models.Model):
    _name = "resource.booking.type"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Resource Booking Type"
    _sql_constraints = [
        ("duration_positive", "CHECK(duration > 0)", "Duration must be positive."),
    ]

    active = fields.Boolean(default=True)
    alarm_ids = fields.Many2many(
        string="Default reminders",
        comodel_name="calendar.alarm",
        help="Meetings will be created with these reminders by default.",
    )
    booking_count = fields.Integer(compute="_compute_booking_count")
    categ_ids = fields.Many2many(
        string="Default tags",
        comodel_name="calendar.event.type",
        help="Meetings will be created with these tags by default.",
    )
    combination_assignment = fields.Selection(
        [
            ("sorted", "Sorted: pick the first one that is free"),
            ("random", "Randomly: order is not important"),
        ],
        required=True,
        default="random",
        help=(
            "Choose how to auto-assign resource combinations. "
            "It has no effect if assigned manually."
        ),
    )
    combination_rel_ids = fields.One2many(
        comodel_name="resource.booking.type.combination.rel",
        inverse_name="type_id",
        string="Available resource combinations",
        copy=True,
        help="Resource combinations available for this type of bookings.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        index=True,
        readonly=False,
        store=True,
        string="Company",
        help="Company where this booking type is available.",
    )
    duration = fields.Float(
        required=True,
        default=0.5,  # 30 minutes
        help=("Booking default duration."),
    )
    slot_duration = fields.Float(
        required=True,
        default=0.5,  # 30 minutes
        help=("Interval offered to start each resource booking."),
    )
    location = fields.Char()
    videocall_location = fields.Char(string="Meeting URL")
    modifications_deadline = fields.Float(
        required=True,
        default=24,
        help=(
            "When this deadline has been exceeded, if a booking was not yet "
            "confirmed, it will be canceled automatically. Also, only booking "
            "managers will be able to unschedule or reschedule them. "
            "The value is expressed in hours."
        ),
    )
    name = fields.Char(index=True, translate=True, required=True)
    booking_ids = fields.One2many(
        comodel_name="resource.booking",
        inverse_name="type_id",
        string="Bookings",
        help="Bookings available for this type",
    )
    resource_calendar_id = fields.Many2one(
        comodel_name="resource.calendar",
        default=lambda self: self._default_resource_calendar(),
        index=True,
        required=True,
        ondelete="restrict",
        string="Availability Calendar",
        help="Restrict bookings to this schedule.",
    )
    requester_advice = fields.Text(
        translate=True,
        help=(
            "Text that will appear by default in portal invitation emails "
            "and in calendar views for scheduling."
        ),
    )

    @api.model
    def _default_resource_calendar(self):
        return self.env.company.resource_calendar_id

    @api.depends("booking_ids")
    def _compute_booking_count(self):
        data = self.env["resource.booking"].read_group(
            [("type_id", "in", self.ids)], ["type_id"], ["type_id"]
        )
        mapping = {x["type_id"][0]: x["type_id_count"] for x in data}
        for one in self:
            one.booking_count = mapping.get(one.id, 0)

    @api.constrains("booking_ids", "resource_calendar_id", "combination_rel_ids")
    def _check_bookings_scheduling(self):
        """Scheduled bookings must have no conflicts."""
        bookings = self.mapped("booking_ids")
        return bookings._check_scheduling()

    def _get_combinations_priorized(self):
        """Gets all combinations sorted by the chosen assignment method."""
        if not self.combination_assignment:
            return self.combination_rel_ids.mapped("combination_id")
        keys = {"sorted": "sequence", "random": lambda *a: random()}
        rels = self.combination_rel_ids.sorted(keys[self.combination_assignment])
        combinations = rels.mapped("combination_id")
        return combinations

    def action_open_bookings(self):
        DurationParser = self.env["ir.qweb.field.duration"]
        return {
            "context": dict(
                self.env.context,
                default_alarm_ids=[(6, 0, self.alarm_ids.ids)],
                default_description=self.requester_advice,
                default_duration=self.duration,
                default_type_id=self.id,
                # Context used by web_calendar_slot_duration module
                calendar_slot_duration=DurationParser.value_to_html(
                    self.slot_duration,
                    {
                        "unit": "hour",
                        "digital": True,
                    },
                ),
            ),
            "domain": [("type_id", "=", self.id)],
            "name": _("Bookings"),
            "res_model": "resource.booking",
            "type": "ir.actions.act_window",
            "view_mode": "calendar,tree,form",
        }
