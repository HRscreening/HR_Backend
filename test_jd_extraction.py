"""
Test script for generate_rubric_from_jd() (single-call rubric pipeline).
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
from src.pipelines.generate_rubric import generate_rubric_from_jd

# Sample JD text for testing
SAMPLE_JD = """
Senior Backend Engineer

We are seeking a highly skilled Senior Backend Engineer to join our engineering team.

Requirements:
- 5+ years of professional software development experience
- Strong proficiency in Python and FastAPI
- Experience with PostgreSQL and Redis
- Knowledge of AWS services (EC2, S3, Lambda)
- Bachelor's degree in Computer Science or related field (required)

Preferred Qualifications:
- Experience with Docker and Kubernetes
- Familiarity with microservices architecture
- Strong communication skills

Responsibilities:
- Design and implement scalable backend systems
- Lead technical discussions and code reviews
- Mentor junior engineers
- Collaborate with product team on feature development

Success Metrics:
- Reduce API latency to <100ms
- Achieve 99.9% uptime
- Deliver features on time with high quality

Constraints:
- Location: San Francisco, CA (Hybrid - 3 days/week in office)
- Must be authorized to work in the United States
- Some travel required (10-15%)

Salary: $150,000 - $200,000 per year
"""


async def test_extraction():
    """Test rubric generation pipeline."""
    print("=" * 60)
    print("Testing Rubric Generation Pipeline (single-call)")
    print("=" * 60)

    try:
        result = await generate_rubric_from_jd(SAMPLE_JD, use_cache=False)

        assert isinstance(result, dict)
        assert "domain" in result
        assert "job_data" in result
        assert "threshold_score" in result
        assert isinstance(result.get("sections"), list)

        print("\n✅ Rubric generation successful!")
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"\n❌ Rubric generation failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_extraction())
