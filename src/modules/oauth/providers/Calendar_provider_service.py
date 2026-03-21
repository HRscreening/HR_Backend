import httpx
from configs.env_config import Calendar_Client_Secret, Calendar_Client_ID, Calendar_Redirect_URI


class GoogleCalendarOAuthService:
    def __init__(self):
        self.client_id = Calendar_Client_ID
        self.client_secret = Calendar_Client_Secret
        self.redirect_uri = Calendar_Redirect_URI

    def get_authorization_url(self, state: str):
        return (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            "&response_type=code"
            "&scope=openid email profile https://www.googleapis.com/auth/calendar"
            "&access_type=offline"
            "&prompt=consent"
            "&include_granted_scopes=true"
            f"&state={state}"
        )

    async def exchange_code_for_tokens(self, code: str):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )

        if response.status_code != 200:
            raise Exception(response.text)

        return response.json()

    async def refresh_access_token(self, refresh_token: str):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

        return response.json()

    async def get_google_user_info(self, access_token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        return response.json()



class OutLookCalendarOAuthService:
    def __init__(self):
        pass