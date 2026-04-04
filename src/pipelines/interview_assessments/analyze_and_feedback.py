from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from src.pipelines.models import chunk_analyzer_model
from src.pipelines.interview_assessments.helpers.prompt import build_chunk_prompt, build_final_prompt
from src.pipelines.interview_assessments.helpers.chunk_helper import chunk_with_overlap
from src.pipelines.interview_assessments.helpers.output_format import FinalFeedbackOutput,ChunkAnalysisOutput
from typing import Optional

class MessagesState(TypedDict):
    transcript: dict
    normalized_sentences: list[dict]
    chunks: list[list[dict]]
    chunk_analysis: list[dict]
    job_criterias: dict
    assessment_parameters : list[str]
    final_analysis: FinalFeedbackOutput

# ! Adjust chunk size and overlap as needed
CHUNK_SIZE = 85 # using high to reduce llm calls, but can be adjusted based on the length of the transcript and the desired granularity of analysis
OVERLAP = 3

# 
def normalize_json(state: MessagesState):
    """Normalize the transcript JSON to a consistent format."""
    transcript = state["transcript"]
    print("Normalizing transcript...")
    normalized = [
        {
            "speaker": s.get("speaker_name", "").lower().strip(),
            "text": s.get("text", "").strip()
        }
        for s in transcript.get("sentences", [])
    ]
    
    return {**state, "normalized_sentences": normalized}



def split_into_chunks(state: MessagesState):
    """Split the normalized sentences into overlapping chunks."""
    sentences = state["normalized_sentences"]
    print("Splitting into chunks...")
    

    chunks = chunk_with_overlap(sentences, chunk_size=CHUNK_SIZE, overlap=OVERLAP) 
    
    return {**state, "chunks": chunks}



async def analyze_chunks(state: MessagesState):
    """Analyze each chunk using the LLM and produce structured evaluations."""
    print("Analyzing chunks...")
    chunks = state["chunks"]
    job_criterias = state["job_criterias"]
    assessment_parameters = state["assessment_parameters"]
    structured_model = chunk_analyzer_model.with_structured_output(ChunkAnalysisOutput)

    results = []

    for chunk in chunks:
        prompt = build_chunk_prompt(
            chunk,
            job_criterias,
            assessment_parameters
        )

        response = await structured_model.ainvoke(prompt)
        results.append(response.model_dump())

    return {"chunk_analysis": results}



async def final_analysis_node(state: MessagesState):
    """Perform final analysis by synthesizing chunk-level evaluations into a comprehensive feedback."""
    print("Performing final analysis...")
    chunk_analysis = state["chunk_analysis"]
    assessment_parameters = state["assessment_parameters"]

    prompt = build_final_prompt(chunk_analysis, assessment_parameters)
    structured_model = chunk_analyzer_model.with_structured_output(FinalFeedbackOutput)
    response = await structured_model.ainvoke(prompt)
    
    parsed = response.model_dump()

    return {"final_analysis": parsed}










graph = StateGraph(MessagesState)

graph.add_node("normalize_json", normalize_json)
graph.add_node("split_into_chunks", split_into_chunks)
graph.add_node("analyze_chunks", analyze_chunks)
graph.add_node("final_analysis_node", final_analysis_node)

graph.add_edge(START, "normalize_json")
graph.add_edge("normalize_json", "split_into_chunks")
graph.add_edge("split_into_chunks", "analyze_chunks")
graph.add_edge("analyze_chunks", "final_analysis_node")
graph.add_edge("final_analysis_node", END)

analyze_pipeline = graph.compile()


from data.transcript import load_test_analysis

async def run_transcript_analysis_pipeline(transcript: dict, assessment_criterias, job_criterias)-> Optional[FinalFeedbackOutput]:
    """Helper function to run the entire analysis pipeline with the given transcript and parameters."""
    try:
     
        result = await analyze_pipeline.ainvoke({
        "transcript": transcript, 
        "assessment_parameters": assessment_criterias,
        "job_criterias": job_criterias 
        })
        
        return result["final_analysis"]

    except Exception as e:
        print(f"Error during Analysis pipeline execution: {e}")
        return None
    
    

# Run



# if __name__ == "__main__":
    
#     trnascript = load_transcript()
#     result = app.invoke({
#         "transcript": trnascript["data"]["transcript"]  # pass here
#     })
#     print(result["chunks"])    
