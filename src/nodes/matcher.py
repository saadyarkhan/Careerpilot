"""
src/graph/nodes/matcher.py

Matcher / Scoring Agent.

Responsibilities:
- Compare structured Resume JSON with structured JD JSON.
- Generate Gemini embeddings.
- Store and query vectors using Pinecone.
- Perform LLM reasoning for matching.
- Generate a final fit score and gap analysis.

Expected Graph State Input:
    state["resume_json"]
    state["jd_json"]

Graph State Output:
    state["score"]
    state["gap_analysis"]
    state["match_analysis"]
"""

import json
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pinecone import Pinecone

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI


load_dotenv()


# ============================================================
# Environment Variables
# ============================================================

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv(
    "PINECONE_INDEX_NAME",
    "careerpilot-matcher",
)


if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is missing.")

if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY is missing.")


# ============================================================
# Gemini Embedding Client
# ============================================================

embedding_client = genai.Client(
    api_key=GOOGLE_API_KEY
)


EMBEDDING_MODEL = "gemini-embedding-001"


# ============================================================
# Pinecone Client
# ============================================================

pinecone_client = Pinecone(
    api_key=PINECONE_API_KEY
)

pinecone_index = pinecone_client.Index(
    PINECONE_INDEX_NAME
)


# ============================================================
# Gemini LLM
# ============================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    google_api_key=GOOGLE_API_KEY,
)


parser = JsonOutputParser()


# ============================================================
# LLM Matching Prompt
# ============================================================

match_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an expert Resume-to-Job Matching Agent.

Your task is to compare a candidate resume with a job description.

Use ONLY the provided Resume JSON and Job Description JSON.

Do not invent candidate skills, experience, or qualifications.

Analyze:

1. Required skill match
2. Preferred skill match
3. Experience match
4. Education match
5. Major gaps
6. Candidate strengths

Return ONLY valid JSON using this exact structure:

{
    "llm_fit_score": 0,
    "strengths": [],
    "matched_skills": [],
    "missing_required_skills": [],
    "missing_preferred_skills": [],
    "experience_gaps": [],
    "education_gaps": [],
    "gap_analysis": "",
    "reasoning": ""
}

The "llm_fit_score" must be an integer between 0 and 100.

Be conservative with the score.
Do not give a high score merely because the candidate has related skills.
""",
        ),
        (
            "human",
            """
RESUME JSON:
{resume_json}

JOB DESCRIPTION JSON:
{jd_json}
""",
        ),
    ]
)


reasoning_chain = match_prompt | llm | parser


# ============================================================
# Helper Functions
# ============================================================

def _json_to_text(data: dict[str, Any]) -> str:
    """
    Convert structured JSON into readable text.
    """

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )


def _generate_embedding(text: str) -> list[float]:
    """
    Generate Gemini embedding.

    Returns:
        Embedding vector as a list of floats.
    """

    response = embedding_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="SEMANTIC_SIMILARITY",
            output_dimensionality=768,
        ),
    )

    return response.embeddings[0].values


def _calculate_pinecone_similarity(
    resume_text: str,
    jd_text: str,
) -> float:
    """
    Store the resume embedding in Pinecone and query it
    using the JD embedding.

    Returns:
        Cosine similarity score.
    """

    resume_embedding = _generate_embedding(
        resume_text
    )

    jd_embedding = _generate_embedding(
        jd_text
    )

    resume_vector_id = f"resume-{uuid.uuid4()}"

    pinecone_index.upsert(
        vectors=[
            {
                "id": resume_vector_id,
                "values": resume_embedding,
                "metadata": {
                    "type": "resume",
                },
            }
        ],
        namespace="careerpilot-matching",
    )

    query_response = pinecone_index.query(
        vector=jd_embedding,
        top_k=1,
        include_metadata=True,
        namespace="careerpilot-matching",
    )

    if not query_response.matches:
        return 0.0

    similarity_score = query_response.matches[0].score

    return float(similarity_score)


def _calculate_final_score(
    semantic_score: float,
    llm_score: int,
) -> int:
    """
    Combine semantic similarity and LLM reasoning score.

    Weighting:
        40% semantic similarity
        60% LLM reasoning
    """

    semantic_score_100 = max(
        0,
        min(
            100,
            semantic_score * 100,
        ),
    )

    final_score = (
        semantic_score_100 * 0.4
        + llm_score * 0.6
    )

    return round(final_score)


# ============================================================
# LangGraph Matcher Node
# ============================================================

def matcher_node(state: dict) -> dict:
    """
    LangGraph Matcher Node.

    Expected input:
        state["resume_json"]
        state["jd_json"]

    Returns:
        Updated graph state containing:

        - score
        - gap_analysis
        - match_analysis
    """

    resume_json = state.get("resume_json")

    jd_json = state.get("jd_json")

    if not resume_json:
        raise ValueError(
            "Resume JSON is missing from graph state."
        )

    if not jd_json:
        raise ValueError(
            "JD JSON is missing from graph state."
        )

    # --------------------------------------------------------
    # Step 1: Convert JSON to text
    # --------------------------------------------------------

    resume_text = _json_to_text(
        resume_json
    )

    jd_text = _json_to_text(
        jd_json
    )

    # --------------------------------------------------------
    # Step 2: Pinecone Semantic Similarity
    # --------------------------------------------------------

    semantic_similarity = _calculate_pinecone_similarity(
        resume_text=resume_text,
        jd_text=jd_text,
    )

    # --------------------------------------------------------
    # Step 3: LLM Reasoning
    # --------------------------------------------------------

    match_analysis = reasoning_chain.invoke(
        {
            "resume_json": json.dumps(
                resume_json,
                ensure_ascii=False,
                indent=2,
            ),
            "jd_json": json.dumps(
                jd_json,
                ensure_ascii=False,
                indent=2,
            ),
        }
    )

    # --------------------------------------------------------
    # Step 4: Final Fit Score
    # --------------------------------------------------------

    llm_score = int(
        match_analysis.get(
            "llm_fit_score",
            0,
        )
    )

    final_score = _calculate_final_score(
        semantic_score=semantic_similarity,
        llm_score=llm_score,
    )

    # --------------------------------------------------------
    # Step 5: Update Graph State
    # --------------------------------------------------------

    state["score"] = final_score

    state["gap_analysis"] = {
        "strengths": match_analysis.get(
            "strengths",
            [],
        ),
        "matched_skills": match_analysis.get(
            "matched_skills",
            [],
        ),
        "missing_required_skills": match_analysis.get(
            "missing_required_skills",
            [],
        ),
        "missing_preferred_skills": match_analysis.get(
            "missing_preferred_skills",
            [],
        ),
        "experience_gaps": match_analysis.get(
            "experience_gaps",
            [],
        ),
        "education_gaps": match_analysis.get(
            "education_gaps",
            [],
        ),
        "summary": match_analysis.get(
            "gap_analysis",
            "",
        ),
    }

    state["match_analysis"] = {
        "semantic_similarity": round(
            semantic_similarity,
            4,
        ),
        "llm_fit_score": llm_score,
        "final_score": final_score,
        "reasoning": match_analysis.get(
            "reasoning",
            "",
        ),
    }

    return state