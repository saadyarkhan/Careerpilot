import json
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from parsing.resume_parser import ResumeParser

load_dotenv()


llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)

parser = JsonOutputParser()


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an expert Resume Parser.

Extract ONLY information present in the resume.

Never invent information.

Return valid JSON.

Required schema:

{
  "name":"",
  "email":"",
  "phone":"",
  "location":"",

  "summary":"",

  "skills":[
  ],

  "experience":[
      {
          "job_title":"",
          "company":"",
          "location":"",
          "start_date":"",
          "end_date":"",
          "duration":"",
          "bullets":[]
      }
  ],

  "education":[
      {
          "degree":"",
          "institution":"",
          "year":""
      }
  ],

  "projects":[
      {
          "title":"",
          "description":"",
          "technologies":[]
      }
  ],

  "certifications":[
  ]
}

Return ONLY JSON.
""",
        ),
        (
            "human",
            "{resume_text}",
        ),
    ]
)


chain = prompt | llm | parser


def resume_parser_node(state: dict):
    """
    LangGraph Resume Parser Node

    Input:
        state["resume_path"]

    Output:
        state["resume_json"]
    """

    resume_path = state["resume_path"]

    extension = resume_path.split(".")[-1].lower()

    if extension == "pdf":
        resume_text = ResumeParser.from_pdf(resume_path)

    elif extension == "docx":
        resume_text = ResumeParser.from_docx(resume_path)

    else:
        raise ValueError("Unsupported resume format.")

    resume_json = chain.invoke(
        {
            "resume_text": resume_text
        }
    )

    state["resume_json"] = resume_json

    return state