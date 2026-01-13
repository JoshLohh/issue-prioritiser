from abc import ABC, abstractmethod
import os
import google.generativeai as genai
import openai 
import json
from typing import List

class Scorer(ABC):
    @abstractmethod
    def score_issue(self, issue: dict) -> dict: 
        pass

class GeminiScorer(Scorer):
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def score_issue(self, issue: dict) -> dict: # Singular score_issue
        print("Scoring with Gemini")
        prompt = f"""
        You are an expert at analyzing GitHub issues. Your task is to score an issue on 'priority' and 'friendliness'.
        
        **CRITICAL INSTRUCTIONS:**
        - You MUST strictly adhere to the provided scoring rubrics.
        - Your scoring must be consistent and repeatable. Given the same issue, you should always produce the same score.
        - Focus SOLELY on the provided issue details and the rubrics. Do not introduce any external knowledge or biases.

        **Scoring Rubrics:**

        **Priority Score (0-10):** Reflects the urgency and importance of an issue.
        - **10 (Critical):** Blocks all core user functionality (e.g., login, checkout), causes data corruption/loss, exposes severe security vulnerabilities, or takes down production services. *Immediate, all-hands-on-deck required.*
        - **8-9 (High):** Impacts a large percentage of users or a critical business flow (e.g., broken search, major UI component failing). Significant degradation in system performance or reliability. Directly affects revenue or critical user workflows.
        - **5-7 (Medium):** Affects a moderate number of users or a non-critical feature. Includes important enhancements that improve efficiency or user experience, or minor bugs with workarounds. (e.g., UI glitch in a rarely used page, adding a small filter option).
        - **2-4 (Low):** Cosmetic issues (e.g., misaligned elements, wrong color), typos, minor UI/UX suggestions, or small, non-disruptive performance improvements. Has little to no impact on core functionality. (e.g., changing button border-radius, updating a tooltip text).
        - **0-1 (Trivial/Backlog):** Purely speculative ideas, very minor aesthetic tweaks, or issues explicitly marked as "won't fix" or "future consideration." No immediate action needed.

        **Friendliness Score (0-10):** Reflects how approachable and suitable an issue is for new contributors.
        - **10 (Perfect First Issue):** Clearly defined task with detailed steps (e.g., "Change button color from blue to green in `src/components/Button.js`"), explicitly labeled "good first issue" or "easy-fix". Requires modifying 1-2 files. Setup instructions are comprehensive and easy to follow.
        - **8-9 (Good for Beginners):** Task involves a single, isolated component or module. Clear problem description and expected outcome. May require slight debugging or understanding of local project conventions. Max 3-5 files involved. Requires basic familiarity with the project's tech stack.
        - **5-7 (Intermediate):** Requires understanding of interconnected components or a specific feature area. Problem might require some investigation to reproduce. Involves moderate logic changes or additions. Good for someone familiar with the tech stack but new to the codebase. (e.g., adding a new field to an existing form, implementing a simple API integration).
        - **2-4 (Challenging):** Involves multiple modules, significant logic changes, or refactoring existing code. Requires debugging complex interactions or understanding architectural patterns. Might affect several parts of the system. Requires solid experience with the tech stack and some codebase familiarity.
        - **0-1 (Expert Level):** Highly complex, touches core architecture, potential for widespread impact, requires expert domain knowledge. Often involves performance optimization, security fixes, or major feature overhauls. (e.g., database schema changes, refactoring core authentication logic).

        **Examples:**

        **Example 1:**
        - **Issue:** Title: "Critical bug: Users can't log in", Labels: "bug", "critical"
        - **Score:** {{"priority_score": 10, "friendliness_score": 2}}

        **Example 2:**
        - **Issue:** Title: "Add a 'good first issue' label to README", Labels: "documentation", "good first issue"
        - **Score:** {{"priority_score": 2, "friendliness_score": 10}}
        
        **Issue to Score:**
        - **Title:** {issue.get("title", "N/A")}
        - **Body:** {issue.get("body", "N/A")}
        - **Labels:** {', '.join([label["name"] for label in issue.get("labels", [])]) or "N/A"}
        - **Comments Count:** {issue.get("comments", 0)}

        **Output:**
        Return your response as a JSON object with two float keys: 'priority_score' and 'friendliness_score'.
        """

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(temperature=0.1)
            )
            # Gemini's response needs to be cleaned of the markdown code block
            cleaned_response = response.text.strip().lstrip("```json").rstrip("```")
            scores = json.loads(cleaned_response)
            
            # Ensure scores are within the 0-10 range
            scores["priority_score"] = max(0.0, min(10.0, float(scores.get("priority_score", 0.0))))
            scores["friendliness_score"] = max(0.0, min(10.0, float(scores.get("friendliness_score", 0.0))))
            
            return scores
        except Exception as e:
            print(f"Error scoring with Gemini: {e}")
            # Re-raise the exception directly, no random fallback
            raise e

class OpenAIScorer(Scorer):
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        self.client = openai.OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini" # User specified gpt-4o-mini

    def score_issue(self, issue: dict) -> dict: # Singular score_issue
        print(f"Scoring issue {issue.get('id')} with OpenAI ({self.model})")
        prompt = f"""
        You are an expert at analyzing GitHub issues. Your task is to score an issue on 'priority' and 'friendliness'.
        
        **CRITICAL INSTRUCTIONS:**
        - You MUST strictly adhere to the provided scoring rubrics.
        - Your scoring must be consistent and repeatable. Given the same issue, you should always produce the same score.
        - Focus SOLELY on the provided issue details and the rubrics. Do not introduce any external knowledge or biases.

        **Scoring Rubrics:**

        **Priority Score (0-10):** Reflects the urgency and importance of an issue.
        - **10 (Critical):** Blocks all core user functionality (e.g., login, checkout), causes data corruption/loss, exposes severe security vulnerabilities, or takes down production services. *Immediate, all-hands-on-deck required.*
        - **8-9 (High):** Impacts a large percentage of users or a critical business flow (e.g., broken search, major UI component failing). Significant degradation in system performance or reliability. Directly affects revenue or critical user workflows.
        - **5-7 (Medium):** Affects a moderate number of users or a non-critical feature. Includes important enhancements that improve efficiency or user experience, or minor bugs with workarounds. (e.g., UI glitch in a rarely used page, adding a small filter option).
        - **2-4 (Low):** Cosmetic issues (e.g., misaligned elements, wrong color), typos, minor UI/UX suggestions, or small, non-disruptive performance improvements. Has little to no impact on core functionality. (e.g., changing button border-radius, updating a tooltip text).
        - **0-1 (Trivial/Backlog):** Purely speculative ideas, very minor aesthetic tweaks, or issues explicitly marked as "won't fix" or "future consideration." No immediate action needed.

        **Friendliness Score (0-10):** Reflects how approachable and suitable an issue is for new contributors.
        - **10 (Perfect First Issue):** Clearly defined task with detailed steps (e.g., "Change button color from blue to green in `src/components/Button.js`"), explicitly labeled "good first issue" or "easy-fix". Requires modifying 1-2 files. Setup instructions are comprehensive and easy to follow.
        - **8-9 (Good for Beginners):** Task involves a single, isolated component or module. Clear problem description and expected outcome. May require slight debugging or understanding of local project conventions. Max 3-5 files involved. Requires basic familiarity with the project's tech stack.
        - **5-7 (Intermediate):** Requires understanding of interconnected components or a specific feature area. Problem might require some investigation to reproduce. Involves moderate logic changes or additions. Good for someone familiar with the tech stack but new to the codebase. (e.g., adding a new field to an existing form, implementing a simple API integration).
        - **2-4 (Challenging):** Involves multiple modules, significant logic changes, or refactoring existing code. Requires debugging complex interactions or understanding architectural patterns. Might affect several parts of the system. Requires solid experience with the tech stack and some codebase familiarity.
        - **0-1 (Expert Level):** Highly complex, touches core architecture, potential for widespread impact, requires expert domain knowledge. Often involves performance optimization, security fixes, or major feature overhauls. (e.g., database schema changes, refactoring core authentication logic).

        **Examples:**

        **Example 1:**
        - **Issue:** Title: "Critical bug: Users can't log in", Labels: "bug", "critical"
        - **Score:** {{"priority_score": 10, "friendliness_score": 2}}

        **Example 2:**
        - **Issue:** Title: "Add a 'good first issue' label to README", Labels: "documentation", "good first issue"
        - **Score:** {{"priority_score": 2, "friendliness_score": 10}}
        
        **Issue to Score:**
        - **Title:** {issue.get("title", "N/A")}
        - **Body:** {issue.get("body", "N/A")}
        - **Labels:** {', '.join([label["name"] for label in issue.get("labels", [])]) or "N/A"}
        - **Comments Count:** {issue.get("comments", 0)}

        **Output:**
        Return your response as a JSON object with two float keys: 'priority_score' and 'friendliness_score'.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}], # Use "user" role for the prompt
                temperature=0.1,
                response_format={"type": "json_object"} # Request JSON object directly
            )
            
            content = response.choices[0].message.content
            scores = json.loads(content)
            
            # Ensure scores are within the 0-10 range
            scores["priority_score"] = max(0.0, min(10.0, float(scores.get("priority_score", 0.0))))
            scores["friendliness_score"] = max(0.0, min(10.0, float(scores.get("friendliness_score", 0.0))))
            
            return scores
        except Exception as e:
            print(f"Error scoring with OpenAI: {e}")
            raise e

def get_scorer() -> Scorer:
    scorer_type = os.environ.get("SCORER_TYPE", "gemini").lower()
    if scorer_type == "openai":
        print("Using OpenAI Scorer")
        return OpenAIScorer()
    elif scorer_type == "gemini":
        print("Using Gemini Scorer")
        return GeminiScorer()
    else:
        raise ValueError(f"Invalid SCORER_TYPE: {scorer_type}. Choose 'openai' or 'gemini'.")

