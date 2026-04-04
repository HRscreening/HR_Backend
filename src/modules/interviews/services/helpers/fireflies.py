from configs.env_config import Fireflies_API_Key, FireFlies_GraphQL_Endpoint
from configs.log_config import get_logger

import httpx
from datetime import datetime

class FirefliesHelper:
    def __init__(self):
        self.api_key = Fireflies_API_Key
        self.logger = get_logger("FirefliesHelper")
        self.url = FireFlies_GraphQL_Endpoint

    async def fetch_transcript(
        self, meeting_id: str
    ) -> tuple[str, dict] | None:
        
        
        
        # ! fireflies provide more details like duration,speakers etc currently we are only using transcript but in future we can use these details for more insights.
        query = """
        query GetMeeting($meetingId: String!) {
          transcript(id: $meetingId) {
            id
            title
            cal_id
            date
            duration
            sentences {
              text
              speaker_name
              start_time
              end_time
            }
          }
        }
        """

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": query,
                        "variables": {"meetingId": meeting_id},
                    },
                    timeout=60, # 1 minute timeout 
                )

            data = response.json()

            if "errors" in data:
                self.logger.error(f"Fireflies API error: {data['errors']}")
                return None

            transcript = data.get("data", {}).get("transcript")

            if not transcript:
                self.logger.warning("Transcript not ready or missing")
                return None

            calendar_id = transcript.get("cal_id", "unknown_calendar")
            
            if not calendar_id:
                self.logger.warning("Calendar ID missing in transcript data")
                # ! fallback metrhod required currently assuming calendar_id is always present.
                calendar_id = "unknown_calendar"
          

            return calendar_id, transcript

        except Exception as e:
            self.logger.exception(f"Error processing meeting {meeting_id}: {e}")
            return None