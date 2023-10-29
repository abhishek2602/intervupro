"""
IntervuPro - AI Interview Assistant

This script allows users to:

Upload company, job and candidate profiles
Automatically generate interview questions
Record and transcribe interviews
Evaluate interviews based on goals
Key Functions:

generate_knowledge_base()
generate_interview_questions()
transcribe_interview()
evaluate_interview()
"""

# Imports

import streamlit as st
import os
import ast

import pandas as pd
import json
import urllib
import time
import re

from io import BytesIO

from dotenv import load_dotenv

load_dotenv()

import docx
import PyPDF2

from audiorecorder import audiorecorder

import boto3

# 0.25 13.25

# Globals

bedrock_client = boto3.client("bedrock-runtime", "us-east-1")

s3_client = boto3.client("s3")
bucket_name = "genailytics-bucket"

transcribe_client = boto3.client("transcribe")

modelId = "anthropic.claude-v2"
accept = "application/json"
contentType = "application/json"

# Helper Functions


def claude_v2_completion(prompt):
    body = {
        "prompt": "Human: " + prompt + " \n\nAssistant:",
        "max_tokens_to_sample": 4000,
        "temperature": 0.2,
        "top_k": 250,
        "top_p": 0.999,
        "anthropic_version": "bedrock-2023-05-31",
    }

    body = json.dumps(body)

    response = bedrock_client.invoke_model(
        body=body.encode("utf-8"), modelId=modelId, accept=accept, contentType=contentType
    )

    response_body = json.loads(response.get("body").read())

    return response_body.get("completion")


def save_and_upload_file(uploaded_file, bucket_name):
    if uploaded_file is not None:
        object_key = f"uploaded_files/{uploaded_file.name}"
        s3_client.put_object(Bucket=bucket_name, Key=object_key, Body=uploaded_file.getvalue())
        return f"s3://{bucket_name}/{object_key}"
    return None


def read_file_from_s3(s3_uri):
    if s3_uri is None:
        return "No S3 URI provided."

    prefix = "uploaded_files/"
    start_index = s3_uri.find(prefix)
    if start_index == -1:
        return "Invalid S3 URI provided."
    object_key = s3_uri[start_index:]
    file_extension = object_key.split(".")[-1].lower()

    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        file_bytes = response["Body"].read()

        if file_extension == "txt":
            text = file_bytes.decode("utf-8")
        elif file_extension == "docx":
            doc = docx.Document(BytesIO(file_bytes))
            text = "\n".join([p.text for p in doc.paragraphs])
        elif file_extension == "pdf":
            pdf_reader = PyPDF2.PdfFileReader(BytesIO(file_bytes))
            text = ""
            for page_num in range(pdf_reader.numPages):
                page = pdf_reader.getPage(page_num)
                text += page.extractText()
        else:
            return f"File type {file_extension} not supported."
        return text
    except Exception as e:
        return f"Error reading file from S3: {e}"


def convert_df_to_wrapped_markdown(df, subset=None):
    if subset is not None:
        df = df[subset]

    if "Answer" in df.columns:
        for index, row in df.iterrows():
            answer = row["Answer"]
            if isinstance(answer, str):
                try:
                    answer = ast.literal_eval(answer)
                except (ValueError, SyntaxError):
                    pass
            if isinstance(answer, list):
                html_list = "<ul>"
                for item in answer:
                    html_list += f"<li>{item}</li>"
                html_list += "</ul>"
                df.at[index, "Answer"] = html_list

    df_styled = df.style.set_properties(**{"text-align": "left", "white-space": "normal", "word-wrap": "break-word"})

    df_html = df_styled.to_html(index=False, escape=False)

    markdown_table = f"""
    <style>
        .dataframe th, .dataframe td {{
            white-space: normal !important;
            word-wrap: break-word !important;
            text-align: left !important;
        }}
    </style>
    {df_html}
    """

    return markdown_table


# Core Business Logic


def generate_knowledge_base(company_profile, job_description, candidate_profile, bucket_name):
    if company_profile is not None and job_description is not None and candidate_profile is not None:
        # Save to S3 and Read from S3 for Company Profile
        company_profile_s3_uri = save_and_upload_file(company_profile, bucket_name)
        company_profile_text = read_file_from_s3(company_profile_s3_uri)

        # Save to S3 and Read from S3 for Job Description
        job_description_s3_uri = save_and_upload_file(job_description, bucket_name)
        job_description_text = read_file_from_s3(job_description_s3_uri)

        # Save to S3 and Read from S3 for Candidate Profile
        candidate_profile_s3_uri = save_and_upload_file(candidate_profile, bucket_name)
        candidate_profile_text = read_file_from_s3(candidate_profile_s3_uri)

        st.success("Knowledge base created")
        return company_profile_text, job_description_text, candidate_profile_text

    else:
        st.warning("Please upload all required files.")
        return None, None, None


def interview_questions_prompt(company_profile, job_description, candidate_profile, goals):
    system_prompt = """You are a seasoned digital marketing manager at NextGen Digital Solutions, bringing over a decade of experience in SEO, PPC, 
    and content strategy to the table. At 35 years old, you have spent the last three years nurturing and expanding the company’s digital marketing department, 
    demonstrating a keen eye for talent and potential. With a Bachelor’s Degree in Business Administration, specializing in Marketing, from the University of 
    Texas at Austin, you combine their educational background with practical experience to lead their team effectively. You are known for being meticulous, analytical, 
    and having a strong ability to identify candidates’ potential through detailed and insightful interviews. Despite your high expectations and the value they place on 
    preparation, you are approachable and value clear communication, creative problem-solving, and unwavering dedication in potential candidates. Outside the professional 
    realm, you immerse yourself in the latest technology trends and digital innovations, regularly attending industry conferences to ensure they are at the forefront of 
    digital marketing knowledge.
    """

    user_prompt = f"""The task is to create a tailored list of five interview questions that are intricately aligned with the 
    Company Profile: {company_profile}
    Job Description: {job_description}
    Candidate’s Profile: {candidate_profile}
    and the Goals of the Interview:{str(goals)} 
    This will ensure a holistic evaluation of the candidate, facilitating an in-depth understanding of their suitability for the SEO Specialist position at NextGen Digital Solutions.
    Also give acceptable answers in bullet points for refernence
    
    Please generate the response in a json format, the keys of the jason should be
    question number, question, answer, alinged goal
    """

    result = '{"Question No":"","Question":"","Answer":"","Aligned Goal":""}'

    return system_prompt + "\n\n" + user_prompt + "\n\nResult template: " + result


def interview_evalution_prompt(transcript, goals):
    system_prompt = """You are an experienced interviewer with a keen ability to assess candidates' 
    skills, experiences, and cultural fit for the company. Your attention to detail and analytical skills 
    enable you to extract valuable insights from written text. You possess a fair and unbiased 
    attitude, ensuring that your evaluation is solely based on the candidate's responses and not 
    influenced by any personal biases.
    """

    user_prompt = f"""You have been given the task of evaluating a candidate based on their 
    performance in a recent interview. The interview has already been conducted, and a 
    transcript of the conversation is available for your review. 
    Your evaluation will play a crucial role in deciding whether the candidate proceeds to 
    the next round of interviews, and at what level they should be placed.
    
    Here is the transcript:
    {transcript}
    
    Read the Transcript Carefully: Start by thoroughly reading the interview transcript. 
    Pay attention to the candidate’s responses, the way they structure their sentences, and 
    their choice of words.
    
    Evaluate Based on Parameters i.e. {goals}: Evaluate the candidate on the parameters, 
    rating them out of 5 for each. Ensure to provide a brief justification for your rating
    
    Provide Overall Feedback: Summarize your observations, highlighting the candidate’s 
    strengths and areas for improvement. Be specific and provide examples from the transcript 
    to back up your points.
    
    Recommendation for Next Round: Based on your evaluation, decide whether to recommend the 
    candidate for the next round of interviews. Clearly state your decision and provide 
    justification.
    
    Recommended Level: Suggest a level or position within the company that you believe would 
    be the best fit for the candidate, based on their performance in the interview.
    """

    result = """
    {
    "evaluation": {
        "communication_skills": {
        "score": 4,
        "comments": "The candidate communicated their ideas clearly and concisely. They were able to articulate their thoughts well, although there were a few instances where they could have been more succinct."
        },
        "technical_knowledge": {
        "score": 3,
        "comments": "The candidate has a good grasp of the technical aspects required for the role, but there were some areas where their knowledge seemed lacking. Additional training may be required."
        },
        "cultural_fit": {
        "score": 4,
        "comments": "The candidate’s values and work style appear to align well with the company’s culture. They demonstrated adaptability and a willingness to collaborate."
        },
        "experience_and_skills": {
        "score": 5,
        "comments": "The candidate has extensive experience and a strong skill set that is highly relevant to the position. They provided concrete examples of their past work."
        },
        "problem_solving_skills": {
        "score": 4,
        "comments": "The candidate showcased strong problem-solving skills and critical thinking. They were able to analyze situations effectively and propose viable solutions."
        },
        "motivation_and_enthusiasm": {
        "score": 5,
        "comments": "The candidate expressed a strong passion for the role and the industry. They seem very eager to contribute to the company and are motivated to succeed."
        }
    },
    "overall_feedback": "The candidate demonstrated strong communication skills, a good cultural fit, and extensive relevant experience. Their technical knowledge and problem-solving skills are solid, though there may be areas that require further development. Their motivation and enthusiasm for the role are commendable.",
    "recommendation_for_next_round": true,
    "justification_for_recommendation": "Given the candidate's strong performance, relevant experience, and alignment with the company culture, I recommend them for the next round of interviews.",
    "recommended_level": "Mid",
    "comments_on_recommended_level": "Based on their experience and skill set, the candidate would be well-suited for a Senior Developer role."
    }
    """

    return system_prompt + "\n\n" + user_prompt + "\n\nResult template: " + result


def transcribe_file(job_name, file_uri, transcribe_client):
    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": file_uri},
        LanguageCode="en-US",
        Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},  # specify the number of speakers if known
    )

    max_tries = 60
    while max_tries > 0:
        max_tries -= 1
        job = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        job_status = job["TranscriptionJob"]["TranscriptionJobStatus"]
        if job_status in ["COMPLETED", "FAILED"]:
            print(f"Job {job_name} is {job_status}.")
            if job_status == "COMPLETED":
                response = urllib.request.urlopen(job["TranscriptionJob"]["Transcript"]["TranscriptFileUri"])
                data = json.loads(response.read())
                return data
            break
        else:
            print(f"Waiting for {job_name}. Current status is {job_status}.")
        time.sleep(10)


# Streamlit app
def app():
    st.title("IntervuPro")

    st.header("Upload Files")
    company_profile = st.file_uploader("Upload Company Profile", type=["txt", "pdf", "docx"])
    job_description = st.file_uploader("Upload Job Description", type=["txt", "pdf", "docx"])
    candidate_profile = st.file_uploader("Upload Candidate Profile", type=["txt", "pdf", "docx"])

    # Initialize session state variables
    if "knowledge_base_generated" not in st.session_state:
        st.session_state["knowledge_base_generated"] = False
    if "interview_questions_generated" not in st.session_state:
        st.session_state["interview_questions_generated"] = False
    if "audio_data" not in st.session_state:
        st.session_state["audio_data"] = None
    if "interview_transcript_generated" not in st.session_state:
        st.session_state["interview_transcript_generated"] = False

    if "company_profile" not in st.session_state:
        st.session_state["company_profile"] = None
    if "job_description" not in st.session_state:
        st.session_state["job_description"] = None
    if "candidates_profile" not in st.session_state:
        st.session_state["candidates_profile"] = None
    if "interview_questions" not in st.session_state:
        st.session_state["interview_questions"] = None
    if "audio" not in st.session_state:
        st.session_state["audio"] = None
    if "transcription" not in st.session_state:
        st.session_state["transcription"] = None
    if "evaluation" not in st.session_state:
        st.session_state["evaluation"] = None

    if st.button("Generate Knowledge Base"):
        with st.spinner("Generating KB..."):
            company_profile, job_description, candidate_profile = generate_knowledge_base(
                company_profile, job_description, candidate_profile, bucket_name
            )
            st.session_state["knowledge_base_generated"] = True
            st.session_state["company_profile"] = company_profile
            st.session_state["job_description"] = job_description
            st.session_state["candidates_profile"] = candidate_profile

    if st.session_state["knowledge_base_generated"]:
        goals = st.multiselect(
            "Select Goals",
            [
                "Technical Skills",
                "Problem-Solving Ability",
                "Learning Ability",
                "Leadership Skills",
                "Communication Skills",
                "Teamwork and Collaboration",
                "Work Ethic",
                "Adaptability",
                "Attention to Detail",
                "Cultural Fit",
                "Emotional Intelligence",
                "Creativity and Innovation",
                "Organizational Skills",
                "Customer Focus",
                "Initiative",
                "Motivation",
                "Reliability and Dependability",
                "Conflict Resolution Skills",
                "Decision-Making Skills",
                "Time Management",
            ],
        )

        if st.button("Generate Interview Questions"):
            with st.spinner("Generating Questions..."):
                with st.expander("Company Profile", expanded=False):
                    st.write(st.session_state["company_profile"])
                with st.expander("Job Description", expanded=False):
                    st.write(st.session_state["job_description"])
                with st.expander("Candidate Profile", expanded=False):
                    st.write(st.session_state["candidates_profile"])
                with st.expander("Show Interview Questions", expanded=False):
                    interview_questions = claude_v2_completion(
                        interview_questions_prompt(company_profile, job_description, candidate_profile, goals)
                    )
                    json_objects = re.findall(r"\{.*?\}", interview_questions, re.DOTALL)
                    json_data = "[" + ",".join(json_objects) + "]"
                    questions_data = json.loads(json_data)
                    interview_questions_df = pd.DataFrame(questions_data)
                    interview_questions_df.columns = [
                        "Question Number",
                        "Question",
                        "Answer Guidelines",
                        "Aligned Goal",
                    ]
                    interview_questions_df["Answer Guidelines"] = interview_questions_df["Answer Guidelines"].apply(
                        lambda x: x.replace("- ", "\n- ")
                    )

                    st.session_state["interview_questions"] = interview_questions_df

                    st.success("Interview Questions Generated Successfully!")
                    st.markdown(
                        convert_df_to_wrapped_markdown(st.session_state["interview_questions"]), unsafe_allow_html=True
                    )
                    st.session_state["interview_questions_generated"] = True

    if st.session_state["interview_questions_generated"]:
        audio = audiorecorder("Click to record", "Click to stop recording")

        if len(audio) > 0:
            st.session_state["audio_recorded"] = True
            # st.audio(audio.export().read())
            audio_buffer = BytesIO()
            audio.export(audio_buffer, format="wav")
            audio_bytes = audio_buffer.getvalue()

            st.session_state["audio"] = audio_bytes

            st.audio(st.session_state["audio"])

            filename = st.text_input("Enter the filename", "interview_recording")

            if filename and st.button("Save Recording"):
                object_key = "audio/" + filename + ".wav"
                s3_client.put_object(Bucket=bucket_name, Key=object_key, Body=audio_bytes)
                st.success(f"Recording saved as {filename}")
                st.session_state["audio_saved"] = True

        else:
            st.error("No audio data found. Please record the audio again.")

    if st.session_state.get("audio_saved"):
        if st.button("Transcribe the Interview"):
            with st.spinner("Transcribing the Interview..."):
                with st.expander("See Transcript", expanded=False):
                    object_key = "audio/" + filename + ".wav"
                    file_uri = f"s3://{bucket_name}/{object_key}"
                    jobName = filename + "_job"
                    transcription_result = transcribe_file(jobName, file_uri, transcribe_client)

                    speaker_segments = transcription_result["results"]["speaker_labels"]["segments"]
                    items = transcription_result["results"]["items"]

                    data = []
                    current_speaker = None
                    current_content = []
                    start_time = None

                    for segment in speaker_segments:
                        for item in segment["items"]:
                            word_info = next(
                                (
                                    word
                                    for word in items
                                    if word["type"] == "pronunciation" and word["start_time"] == item["start_time"]
                                ),
                                None,
                            )
                            if word_info:
                                if current_speaker != item["speaker_label"]:
                                    if current_speaker is not None:
                                        data.append(
                                            {
                                                "timestamp": start_time,
                                                "speaker": current_speaker,
                                                "speaker_content": " ".join(current_content),
                                            }
                                        )
                                    start_time = item["start_time"]
                                    current_speaker = item["speaker_label"]
                                    current_content = [word_info["alternatives"][0]["content"]]
                                else:
                                    current_content.append(word_info["alternatives"][0]["content"])

                    if current_speaker is not None:
                        data.append(
                            {
                                "timestamp": start_time,
                                "speaker": current_speaker,
                                "speaker_content": " ".join(current_content),
                            }
                        )

                    df = pd.DataFrame(data)

                    st.session_state["transcription"] = df

                    for index, row in st.session_state["transcription"].iterrows():
                        with st.container():
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                st.image("/Users/abhishek/genailytics/5856.jpg", width=100)
                            with col2:
                                st.text_area(
                                    f"{row['speaker']}",
                                    value=row["speaker_content"],
                                    height=100,
                                    key=index,
                                    disabled=True,
                                )

                    st.session_state["interview_transcript_generated"] = True

                    st.success("Interview Transcribed Successfully!")

    if st.session_state["interview_transcript_generated"]:
        if st.button("Evalute the Interview"):
            with st.spinner("Evaluating the Interview..."):
                df = st.session_state["transcription"]
                conversation_string = ""
                for index, row in df.iterrows():
                    conversation_string += f"{row['speaker']}: {row['speaker_content']}\n"

                interview_evaluation = claude_v2_completion(interview_evalution_prompt(conversation_string, goals))
                json_data_match = re.search(r"\{.*\}", interview_evaluation, re.DOTALL)
                json_data = json_data_match.group(0) if json_data_match else "{}"
                # json_data = interview_evaluation.split("\n\n", 1)[1]
                evaluation_data = json.loads(json_data)

                st.session_state["evaluation"] = evaluation_data

                st.json(st.session_state["evaluation"])
                st.write(interview_evaluation)
                st.success("Interview Evaluated Successfully!")


if __name__ == "__main__":
    app()
