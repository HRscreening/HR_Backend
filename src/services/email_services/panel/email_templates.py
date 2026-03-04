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
              {content}
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
</html>"""


def _cta_button(url: str, label: str) -> str:
    """Renders a call-to-action button that works across major email clients."""
    return f"""\
            <table role="presentation" cellpadding="0" cellspacing="0" style="margin:28px auto;">
            <tr>
                <td align="center" style="border-radius:6px;background-color:#4f46e5;">
                <a href="{url}" target="_blank"
                    style="display:inline-block;padding:14px 32px;color:#ffffff;font-size:15px;
                            font-weight:600;text-decoration:none;border-radius:6px;
                            background-color:#4f46e5;letter-spacing:0.3px;">
                    {label}
                </a>
                </td>
            </tr>
            </table>"""


class PanelEmailTemplates:
    """HTML email templates for panelist communications."""

    @staticmethod
    def get_panelist_available_slots_email_template(
        panelist_name: str | None,
        interview_round_title: str,
        form_link: str,
    ) -> str:
        """HTML email asking a panelist to submit their available slots."""

        greeting = panelist_name if panelist_name else "Sir/Madam"

        content = f"""\
                        <p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.7;">
                        Dear <strong>{greeting}</strong>,
                        </p>
                        <p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.7;">
                        You have been selected as a panelist for the
                        <strong style="color:#4f46e5;">{interview_round_title}</strong> round.
                        We sincerely appreciate your support and time.
                        </p>
                        <p style="margin:0 0 8px;font-size:15px;color:#374151;line-height:1.7;">
                        Please share your availability by selecting suitable time slots using the button below:
                        </p>
                        {_cta_button(form_link, "Submit Your Availability &rarr;")}
                        <p style="margin:0 0 16px;font-size:14px;color:#6b7280;line-height:1.7;">
                        If none of the available slots work for you, feel free to suggest alternative times
                        at your convenience.
                        </p>
                        <p style="margin:0 0 4px;font-size:14px;color:#6b7280;line-height:1.7;">
                        We request you to respond at your earliest so we can finalize the schedule.
                        </p>
                        <p style="margin:24px 0 0;font-size:15px;color:#374151;line-height:1.7;">
                        Thank you,<br/>
                        <strong>HR Team</strong>
                        </p>"""

        return _base_html(content)

    @staticmethod
    def panelist_invitation_email_template(
        candidate_name: str,
        interview_round_name: str,
        interview_date: str,
        interview_time: str,
        interview_mode: str,
        interview_link: str,
    ) -> str:
        """HTML email with confirmed interview details sent to the panelist/candidate."""

        content = f"""\
            <p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.7;">
            Dear <strong>{candidate_name}</strong>,
            </p>
            <p style="margin:0 0 20px;font-size:15px;color:#374151;line-height:1.7;">
            We are pleased to inform you that you have been shortlisted for the
            <strong style="color:#4f46e5;">{interview_round_name}</strong> round.
            </p>
            <table role="presentation" cellpadding="0" cellspacing="0"
                style="width:100%;margin-bottom:24px;border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;">
            <tr>
                <td style="padding:12px 16px;background-color:#f9fafb;font-size:13px;color:#6b7280;font-weight:600;width:120px;border-bottom:1px solid #e5e7eb;">
                Date
                </td>
                <td style="padding:12px 16px;font-size:14px;color:#374151;border-bottom:1px solid #e5e7eb;">
                {interview_date}
                </td>
            </tr>
            <tr>
                <td style="padding:12px 16px;background-color:#f9fafb;font-size:13px;color:#6b7280;font-weight:600;border-bottom:1px solid #e5e7eb;">
                Time
                </td>
                <td style="padding:12px 16px;font-size:14px;color:#374151;border-bottom:1px solid #e5e7eb;">
                {interview_time}
                </td>
            </tr>
            <tr>
                <td style="padding:12px 16px;background-color:#f9fafb;font-size:13px;color:#6b7280;font-weight:600;">
                Mode
                </td>
                <td style="padding:12px 16px;font-size:14px;color:#374151;">
                {interview_mode}
                </td>
            </tr>
            </table>
            {_cta_button(interview_link, "Join Interview &rarr;")}
            <p style="margin:0 0 16px;font-size:14px;color:#6b7280;line-height:1.7;">
            Please be available at the scheduled time. If the interview is online, ensure you have
            a stable internet connection.
            </p>
            <p style="margin:0 0 4px;font-size:14px;color:#6b7280;line-height:1.7;">
            If you need to reschedule, please don't hesitate to contact us.
            </p>
            <p style="margin:24px 0 0;font-size:15px;color:#374151;line-height:1.7;">
            Best regards,<br/>
            <strong>HR Team</strong>
            </p>"""

        return _base_html(content)


    @staticmethod
    def get_panelist_booking_confirmation_template(
        panelist_name: str | None,
        candidate_name: str,
        interview_round_title: str,
        interview_date: str,
        interview_time: str,
        meet_link: str | None,
    ) -> str:
        """HTML email notifying a panelist that a candidate has booked a slot."""

        greeting = panelist_name if panelist_name else "Sir/Madam"

        meet_row = ""
        if meet_link:
            meet_row = f"""\
            <tr>
                <td style="padding:12px 16px;background-color:#f9fafb;font-size:13px;color:#6b7280;font-weight:600;width:120px;">
                Meet Link
                </td>
                <td style="padding:12px 16px;font-size:14px;color:#374151;">
                <a href="{meet_link}" style="color:#4f46e5;text-decoration:none;">{meet_link}</a>
                </td>
            </tr>"""

        content = f"""\
            <p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.7;">
            Dear <strong>{greeting}</strong>,
            </p>
            <p style="margin:0 0 20px;font-size:15px;color:#374151;line-height:1.7;">
            A candidate has booked an interview slot with you for the
            <strong style="color:#4f46e5;">{interview_round_title}</strong> round.
            </p>
            <table role="presentation" cellpadding="0" cellspacing="0"
                style="width:100%;margin-bottom:24px;border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;">
            <tr>
                <td style="padding:12px 16px;background-color:#f9fafb;font-size:13px;color:#6b7280;font-weight:600;width:120px;border-bottom:1px solid #e5e7eb;">
                Candidate
                </td>
                <td style="padding:12px 16px;font-size:14px;color:#374151;border-bottom:1px solid #e5e7eb;">
                {candidate_name}
                </td>
            </tr>
            <tr>
                <td style="padding:12px 16px;background-color:#f9fafb;font-size:13px;color:#6b7280;font-weight:600;width:120px;border-bottom:1px solid #e5e7eb;">
                Date
                </td>
                <td style="padding:12px 16px;font-size:14px;color:#374151;border-bottom:1px solid #e5e7eb;">
                {interview_date}
                </td>
            </tr>
            <tr>
                <td style="padding:12px 16px;background-color:#f9fafb;font-size:13px;color:#6b7280;font-weight:600;width:120px;border-bottom:1px solid #e5e7eb;">
                Time
                </td>
                <td style="padding:12px 16px;font-size:14px;color:#374151;border-bottom:1px solid #e5e7eb;">
                {interview_time}
                </td>
            </tr>
            {meet_row}
            </table>
            <p style="margin:0 0 16px;font-size:14px;color:#6b7280;line-height:1.7;">
            Please ensure you are available at the scheduled time. If the interview is online,
            keep your meeting link ready.
            </p>
            <p style="margin:24px 0 0;font-size:15px;color:#374151;line-height:1.7;">
            Thank you,<br/>
            <strong>HR Team</strong>
            </p>"""

        return _base_html(content)


panelist_email_templates = PanelEmailTemplates()