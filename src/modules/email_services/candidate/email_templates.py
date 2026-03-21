def _base_html(content: str) -> str:
    """Wraps email content in a responsive HTML shell with consistent styling."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Email</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f7;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f7;">
    <tr>
      <td align="center" style="padding:30px 10px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
               style="background-color:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.07);">
          <!-- Header -->
          <tr>
            <td style="background-color:#4f46e5;padding:24px 32px;">
              <h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:600;letter-spacing:0.3px;">
                DeskZero HR
              </h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              {{content}}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px;background-color:#f9fafb;border-top:1px solid #e5e7eb;">
              <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.6;">
                This is an automated message from DeskZero HR. Please do not reply directly to this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>""".replace("{content}", content)


def _cta_button(url: str, label: str) -> str:
    """Renders a call-to-action button that works across major email clients."""
    return f"""\
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:28px auto;">
  <tr>
    <td align="center" style="background-color:#4f46e5;border-radius:6px;">
      <a href="{url}" target="_blank"
         style="display:inline-block;padding:14px 32px;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;border-radius:6px;">
        {label}
      </a>
    </td>
  </tr>
</table>"""


class CandidateEmailTemplates:

    @staticmethod
    def get_booking_link_email_template(
        candidate_name: str,
        interview_round_title: str,
        booking_link: str,
    ) -> str:
        content = f"""\
<h2 style="margin:0 0 16px;font-size:18px;color:#1f2937;">
  Your Interview Slots Are Ready
</h2>
<p style="margin:0 0 12px;font-size:15px;color:#374151;line-height:1.6;">
  Hi {candidate_name},
</p>
<p style="margin:0 0 12px;font-size:15px;color:#374151;line-height:1.6;">
  Great news! Available time slots for your <strong>{interview_round_title}</strong> interview
  are now ready. Please select a slot that works best for you.
</p>
{_cta_button(booking_link, "Pick Your Interview Slot")}
<p style="margin:0 0 8px;font-size:13px;color:#6b7280;line-height:1.5;">
  If you have any questions, please contact us at the email address provided in your application.
</p>"""
        return _base_html(content)

    @staticmethod
    def get_booking_confirmation_email_template(
        candidate_name: str,
        interview_round_title: str,
        scheduled_start: str,
        scheduled_end: str,
        meet_link: str | None = None,
        reschedule_link: str | None = None,
    ) -> str:
        meeting_info = ""
        if meet_link:
            meeting_info = f"""\
<p style="margin:0 0 12px;font-size:15px;color:#374151;line-height:1.6;">
  <strong>Meeting Link:</strong>
  <a href="{meet_link}" style="color:#4f46e5;text-decoration:underline;">{meet_link}</a>
</p>"""

        reschedule_info = ""
        if reschedule_link:
            reschedule_info = f"""\
<p style="margin:16px 0 0;font-size:13px;color:#6b7280;line-height:1.5;">
  Need to change the time?
  <a href="{reschedule_link}" style="color:#4f46e5;text-decoration:underline;">Reschedule your interview</a>
</p>"""

        content = f"""\
<h2 style="margin:0 0 16px;font-size:18px;color:#1f2937;">
  Interview Confirmed!
</h2>
<p style="margin:0 0 12px;font-size:15px;color:#374151;line-height:1.6;">
  Hi {candidate_name},
</p>
<p style="margin:0 0 12px;font-size:15px;color:#374151;line-height:1.6;">
  Your <strong>{interview_round_title}</strong> interview has been confirmed.
</p>
<table role="presentation" cellpadding="0" cellspacing="0"
       style="margin:20px 0;background-color:#f9fafb;border-radius:6px;border:1px solid #e5e7eb;width:100%;">
  <tr>
    <td style="padding:16px;">
      <p style="margin:0 0 8px;font-size:14px;color:#6b7280;">Start</p>
      <p style="margin:0 0 16px;font-size:16px;color:#1f2937;font-weight:600;">{scheduled_start}</p>
      <p style="margin:0 0 8px;font-size:14px;color:#6b7280;">End</p>
      <p style="margin:0;font-size:16px;color:#1f2937;font-weight:600;">{scheduled_end}</p>
    </td>
  </tr>
</table>
{meeting_info}
<p style="margin:0 0 12px;font-size:15px;color:#374151;line-height:1.6;">
  Please be prepared and join on time. Good luck!
</p>
{reschedule_info}"""
        return _base_html(content)
      
      
    @staticmethod
    def get_reschedule_new_slots_email_template(
        candidate_name: str,
        interview_round_title: str,
        scheduled_start,
        scheduled_end,
        reschedule_link: str,
        reason: str | None = None,
    ) -> str:
      """
      Email to inform candidate that their interview has been moved to a new time,
      with an option to review or request a different time if needed.
      """

      reason_text = (
          f"<p style=\"margin:0 0 12px;font-size:14px;color:#ef4444;line-height:1.6;\">Reason: {reason}</p>"
          if reason else ""
      )

      content = f"""
          <h2 style=\"margin:0 0 16px;font-size:18px;color:#1f2937;\">Interview Schedule Updated</h2>

          <p style=\"margin:0 0 12px;font-size:15px;color:#374151;line-height:1.6;\">Hi {candidate_name},</p>

          <p style=\"margin:0 0 12px;font-size:15px;color:#374151;line-height:1.6;\">
              Your <strong>{interview_round_title}</strong> interview has been moved to the following time:
          </p>

          <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\"
                style=\"margin:20px 0;background-color:#f9fafb;border-radius:6px;border:1px solid #e5e7eb;width:100%;\">
            <tr>
              <td style=\"padding:16px;\">
                <p style=\"margin:0 0 8px;font-size:14px;color:#6b7280;\">Start</p>
                <p style=\"margin:0 0 16px;font-size:16px;color:#1f2937;font-weight:600;\">{scheduled_start}</p>

                <p style=\"margin:0 0 8px;font-size:14px;color:#6b7280;\">End</p>
                <p style=\"margin:0;font-size:16px;color:#1f2937;font-weight:600;\">{scheduled_end}</p>
              </td>
            </tr>
          </table>

          {reason_text}

          <p style=\"margin:0 0 12px;font-size:15px;color:#374151;line-height:1.6;\">
              If this new time works for you, no action is required.
              If you would like to request a different time, you can manage your schedule using the link below.
          </p>

          {_cta_button(reschedule_link, "Manage Interview Schedule")}

          <p style=\"margin:16px 0 8px;font-size:13px;color:#6b7280;line-height:1.5;\">
              We apologize for any inconvenience and appreciate your understanding.
          </p>
      """

      return _base_html(content)

candidate_email_templates = CandidateEmailTemplates()
