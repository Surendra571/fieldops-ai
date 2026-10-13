from dataclasses import dataclass
from enum import Enum
from typing import Any

from jinja2 import Template


class NotificationTemplateType(str, Enum):
    BOOKING_CONFIRMATION = "BOOKING_CONFIRMATION"
    APPOINTMENT_REMINDER_24H = "APPOINTMENT_REMINDER_24H"
    APPOINTMENT_REMINDER_2H = "APPOINTMENT_REMINDER_2H"
    TECHNICIAN_ASSIGNED = "TECHNICIAN_ASSIGNED"
    APPOINTMENT_RESCHEDULED = "APPOINTMENT_RESCHEDULED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    WORK_ORDER_COMPLETED = "WORK_ORDER_COMPLETED"


@dataclass(frozen=True)
class RenderedNotification:
    template_type: NotificationTemplateType
    sms_body: str
    email_subject: str
    email_html: str
    email_text: str


TEMPLATES: dict[NotificationTemplateType, dict[str, str]] = {
    NotificationTemplateType.BOOKING_CONFIRMATION: {
        "sms": (
            "FieldOps AI: Your appointment for {{ category }} service is confirmed for "
            "{{ scheduled_time }}. Tech: {{ technician_name }}. Details: {{ tracking_url }}"
        ),
        "email_subject": "Confirmed: Your {{ category }} Service Appointment on {{ scheduled_date }}",
        "email_text": (
            "Hello {{ customer_name }},\n\n"
            "Your appointment for {{ category }} service has been confirmed.\n\n"
            "Date & Time: {{ scheduled_time }}\n"
            "Technician: {{ technician_name }}\n"
            "Service Address: {{ service_address }}\n"
            "Work Order #: {{ work_order_number }}\n\n"
            "Track or modify your appointment here: {{ tracking_url }}\n\n"
            "Thank you for choosing FieldOps AI."
        ),
        "email_html": (
            "<h2>Your Service Appointment is Confirmed</h2>"
            "<p>Hello <strong>{{ customer_name }}</strong>,</p>"
            "<p>Your service request has been scheduled with our certified technician.</p>"
            "<table style='border-collapse: collapse; margin: 16px 0;'>"
            "<tr><td><strong>Date & Time:</strong></td><td>{{ scheduled_time }}</td></tr>"
            "<tr><td><strong>Technician:</strong></td><td>{{ technician_name }}</td></tr>"
            "<tr><td><strong>Service Address:</strong></td><td>{{ service_address }}</td></tr>"
            "<tr><td><strong>Work Order #:</strong></td><td>{{ work_order_number }}</td></tr>"
            "</table>"
            "<p><a href='{{ tracking_url }}' style='background:#0d6efd;color:#fff;padding:10px 18px;text-decoration:none;border-radius:4px;'>View Appointment Details</a></p>"
        ),
    },
    NotificationTemplateType.APPOINTMENT_REMINDER_24H: {
        "sms": (
            "FieldOps AI Reminder: Your {{ category }} appointment is tomorrow at "
            "{{ scheduled_time }}. Reply C to confirm or call to reschedule."
        ),
        "email_subject": "Reminder: Upcoming Service Appointment Tomorrow at {{ scheduled_time }}",
        "email_text": (
            "Hello {{ customer_name }},\n\n"
            "This is a reminder that your {{ category }} appointment is scheduled for tomorrow at {{ scheduled_time }}.\n"
            "Technician: {{ technician_name }}\n"
            "Address: {{ service_address }}\n\n"
            "If you need to make changes, please visit: {{ tracking_url }}"
        ),
        "email_html": (
            "<h2>Reminder: Your Appointment is Tomorrow</h2>"
            "<p>Hello {{ customer_name }},</p>"
            "<p>Our technician <strong>{{ technician_name }}</strong> is scheduled to arrive tomorrow at <strong>{{ scheduled_time }}</strong>.</p>"
            "<p>Address: {{ service_address }}</p>"
            "<p><a href='{{ tracking_url }}'>Manage Appointment</a></p>"
        ),
    },
    NotificationTemplateType.APPOINTMENT_REMINDER_2H: {
        "sms": (
            "FieldOps AI: Technician {{ technician_name }} will arrive in approx. 2 hours "
            "for your {{ category }} service at {{ service_address }}."
        ),
        "email_subject": "Technician Arriving Soon (Approx. 2 Hours)",
        "email_text": (
            "Hello {{ customer_name }},\n\n"
            "Technician {{ technician_name }} is preparing for your appointment at {{ scheduled_time }}.\n"
            "Address: {{ service_address }}\n\n"
            "Live tracking: {{ tracking_url }}"
        ),
        "email_html": (
            "<h2>Technician Arriving Soon</h2>"
            "<p>Hello {{ customer_name }}, technician <strong>{{ technician_name }}</strong> will arrive at approximately <strong>{{ scheduled_time }}</strong>.</p>"
            "<p><a href='{{ tracking_url }}'>Track Technician Status</a></p>"
        ),
    },
    NotificationTemplateType.TECHNICIAN_ASSIGNED: {
        "sms": (
            "FieldOps AI: Technician {{ technician_name }} has been assigned to your {{ category }} "
            "request ({{ work_order_number }}). Scheduled: {{ scheduled_time }}."
        ),
        "email_subject": "Technician Assigned to Work Order #{{ work_order_number }}",
        "email_text": (
            "Hello {{ customer_name }},\n\n"
            "Technician {{ technician_name }} has been assigned to your service request ({{ work_order_number }}).\n"
            "Scheduled Time: {{ scheduled_time }}\n"
            "Details: {{ tracking_url }}"
        ),
        "email_html": (
            "<h2>Technician Assigned</h2>"
            "<p>Technician <strong>{{ technician_name }}</strong> has been assigned to your {{ category }} request.</p>"
            "<p>Scheduled Time: {{ scheduled_time }}</p>"
            "<p><a href='{{ tracking_url }}'>View Work Order</a></p>"
        ),
    },
    NotificationTemplateType.APPOINTMENT_RESCHEDULED: {
        "sms": (
            "FieldOps AI: Your {{ category }} appointment has been rescheduled to "
            "{{ new_scheduled_time }}. Details: {{ tracking_url }}"
        ),
        "email_subject": "Updated: Your Appointment Has Been Rescheduled to {{ new_scheduled_time }}",
        "email_text": (
            "Hello {{ customer_name }},\n\n"
            "Your appointment has been successfully rescheduled.\n\n"
            "New Time: {{ new_scheduled_time }}\n"
            "Technician: {{ technician_name }}\n"
            "Reason: {{ reason }}\n\n"
            "Details: {{ tracking_url }}"
        ),
        "email_html": (
            "<h2>Appointment Rescheduled</h2>"
            "<p>Hello {{ customer_name }}, your appointment has been updated to <strong>{{ new_scheduled_time }}</strong>.</p>"
            "<p>Reason: {{ reason }}</p>"
            "<p><a href='{{ tracking_url }}'>Review Changes</a></p>"
        ),
    },
    NotificationTemplateType.APPOINTMENT_CANCELLED: {
        "sms": (
            "FieldOps AI: Your appointment for {{ category }} on {{ scheduled_time }} has been cancelled. "
            "To rebook, visit {{ tracking_url }}"
        ),
        "email_subject": "Cancelled: Service Appointment on {{ scheduled_date }}",
        "email_text": (
            "Hello {{ customer_name }},\n\n"
            "Your appointment on {{ scheduled_time }} has been cancelled.\n"
            "Reason: {{ reason }}\n\n"
            "If you would like to book a new appointment, visit: {{ tracking_url }}"
        ),
        "email_html": (
            "<h2>Appointment Cancelled</h2>"
            "<p>Your service appointment on {{ scheduled_time }} has been cancelled.</p>"
            "<p>Reason: {{ reason }}</p>"
            "<p><a href='{{ tracking_url }}'>Book a New Appointment</a></p>"
        ),
    },
    NotificationTemplateType.WORK_ORDER_COMPLETED: {
        "sms": (
            "FieldOps AI: Work order {{ work_order_number }} is complete! "
            "Please rate your service with {{ technician_name }}: {{ review_url }}"
        ),
        "email_subject": "Service Complete: Work Order #{{ work_order_number }}",
        "email_text": (
            "Hello {{ customer_name }},\n\n"
            "Technician {{ technician_name }} has completed your {{ category }} service.\n\n"
            "Work Order: {{ work_order_number }}\n"
            "Completion Summary: {{ completion_notes }}\n\n"
            "Review your service report and rate technician: {{ review_url }}\n\n"
            "Thank you for using FieldOps AI!"
        ),
        "email_html": (
            "<h2>Service Complete</h2>"
            "<p>Hello {{ customer_name }}, your service request has been completed.</p>"
            "<p><strong>Summary:</strong> {{ completion_notes }}</p>"
            "<p><a href='{{ review_url }}' style='background:#198754;color:#fff;padding:10px 18px;text-decoration:none;border-radius:4px;'>View Invoice & Rate Service</a></p>"
        ),
    },
}


class NotificationTemplateService:
    """
    Renders multi-channel notification templates with Jinja2.
    """

    @classmethod
    def render(
        cls, template_type: NotificationTemplateType, context: dict[str, Any]
    ) -> RenderedNotification:
        raw = TEMPLATES.get(template_type)
        if not raw:
            raise ValueError(f"Unknown notification template: {template_type}")

        # Default fallbacks
        safe_ctx = {
            "customer_name": "Valued Customer",
            "category": "Maintenance",
            "technician_name": "Field Technician",
            "service_address": "",
            "work_order_number": "",
            "scheduled_time": "",
            "scheduled_date": "",
            "new_scheduled_time": "",
            "reason": "Customer request",
            "tracking_url": "https://fieldops.ai/appointments/view",
            "review_url": "https://fieldops.ai/feedback",
            "completion_notes": "All requested repairs completed successfully.",
        }
        safe_ctx.update(context)

        sms_body = Template(raw["sms"]).render(safe_ctx)
        subject = Template(raw["email_subject"]).render(safe_ctx)
        text = Template(raw["email_text"]).render(safe_ctx)
        html = Template(raw["email_html"]).render(safe_ctx)

        return RenderedNotification(
            template_type=template_type,
            sms_body=sms_body.strip(),
            email_subject=subject.strip(),
            email_html=html.strip(),
            email_text=text.strip(),
        )
