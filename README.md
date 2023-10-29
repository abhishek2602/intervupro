# IntervuPro

## Overview

IntervuPro is an innovative AI-driven interview platform designed to streamline the hiring process. Leveraging the powerful capabilities of the Claude AI model, our solution automates the generation of personalized interview questions, facilitates audio recording of interviews, and provides comprehensive evaluations based on predefined goals and parameters. The end-to-end solution ensures a seamless and efficient experience for both interviewers and candidates, significantly enhancing the quality of candidate assessments.

## Features

- **Profile Management**: Upload and manage company, job, and candidate profiles with ease.
- **AI-Driven Question Generation**: Generate tailored interview questions based on profiles and interview goals.
- **Interview Recording**: Record interviews directly through the app, with audio files saved securely.
- **Transcription Services**: Utilize AWS Transcribe for accurate speech-to-text conversion.
- **Interview Evaluation**: Obtain comprehensive evaluations of interviews, including scores, comments, and recommendations.
- **Data Review**: Access and review interview questions, audio, transcripts, and evaluations all in one place.

## Getting Started

### Prerequisites

- Ensure you have Python installed on your machine.
- An AWS account set up with access to S3 and AWS Transcribe.

### Installation

1. Clone the repository:

```git clone https://github.com/GenAIlytics/IntervuPro.git```

2. Navigate to the project directory:

```cd IntervuPro/streamlit_app```

3. Install the required dependencies:

```pip install -r requirements.txt```

4. Run the Streamlit app:
5. 
```streamlit run app.py```


## Usage

Follow the on-screen instructions in the Streamlit app to upload profiles, generate interview questions, record interviews, and review evaluations.

## Built With

- [Streamlit](https://streamlit.io/) - For the frontend.
- [AWS S3](https://aws.amazon.com/s3/) - For storing profiles, audio recordings, and transcripts.
- [AWS Transcribe](https://aws.amazon.com/transcribe/) - For audio transcription.
- [Claude AI](https://www.anthropic.com/index/claude-2) - For generating interview questions and evaluations.
- [Amazon Bedrock](https://aws.amazon.com/bedrock/) - TO get access to Anthropic Claude model.
- [DataRobot](https://www.datarobot.com/) - For building endpoints to use Amazon Bedrock models.

