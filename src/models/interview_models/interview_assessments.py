
# #### `interview_assessments`

# Post-interview feedback from each panelist.

# | Column | Type | Constraints | Description |
# |--------|------|-------------|-------------|
# | `id` | UUID | PK, default uuid4 | |
# | `interview_id` | UUID | FK → interviews.id, NOT NULL | |
# | `panelist_email` | String(320) | NOT NULL | |
# | `panelist_name` | String(200) | NULL | |
# | `rating` | Enum(FeedbackRating) | NOT NULL | strong_yes, yes, neutral, no, strong_no |
# | `technical_score` | Integer | NULL | 1–10 (optional) |
# | `communication_score` | Integer | NULL | 1–10 (optional) |
# | `culture_fit_score` | Integer | NULL | 1–10 (optional) |
# | `strengths` | Text | NULL | Free text |
# | `concerns` | Text | NULL | Free text |
# | `notes` | Text | NULL | General notes |
# | `recommendation` | Text | NULL | Hire / No hire / Next round |
# | `feedback_token` | String(500) | NULL | Signed JWT for feedback form link |
# | `token_expires_at` | DateTime | NULL | |
# | `submitted_at` | DateTime | NULL | |
# | `created_at` | DateTime | NOT NULL, default now | |

# **Constraints**: UNIQUE(interview_id, panelist_email)


# TODO: Implement this model and related repository functions for creating/updating feedback, generating feedback tokens, etc.