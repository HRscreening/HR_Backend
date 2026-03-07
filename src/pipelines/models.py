from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_openai import ChatOpenAI

# llm = ChatOpenAI(
#     # model="gpt-5-nano",   # ✅ or "gpt-5-nano" if your account has access
#     model="gpt-4o-mini-2024-07-18",   # ✅ or "gpt-5-nano" if your account has access
#     # temperature=0,
#     max_tokens=1024
# )


from google import genai

client = genai.Client()

# Gemini model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    # max_output_tokens=2048
)


image_reader_model = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    temperature=0,
)



scoring_model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    # model="gemini-2.5-flash",
    temperature=0,
    # max_output_tokens=2048
)








