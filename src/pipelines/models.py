from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_openai import ChatOpenAI

# llm = ChatOpenAI(
#     # model="gpt-5-nano",   # ✅ or "gpt-5-nano" if your account has access
#     model="gpt-4o-mini-2024-07-18",   # ✅ or "gpt-5-nano" if your account has access
#     # temperature=0,
#     max_tokens=1024
# )




# Gemini model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    # max_output_tokens=2048
)



scoring_model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    # model="gemini-2.5-flash",
    temperature=0,
    # max_output_tokens=2048
)






