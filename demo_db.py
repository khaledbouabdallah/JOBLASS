"""
Example usage of JOBLASS database
Run this to initialize the database and see example operations
"""
from joblass.db import init_db, Job, Application, Score
from joblass.db import JobRepository, ApplicationRepository, ScoreRepository
from datetime import datetime


def demo_database():
    """Demonstrate database operations"""
    
    print("=" * 60)
    print("JOBLASS Database Demo")
    print("=" * 60)
    
    # Initialize database
    print("\n1. Initializing database...")
    init_db()
    print("✅ Database initialized")
    
    # Create sample jobs
    print("\n2. Creating sample jobs...")
    
    job1 = Job(
        title="Machine Learning Intern",
        company="Mirakl",
        location="Paris, France",
        url="https://glassdoor.com/job/123456",
        source="glassdoor",
        description="Work on LLM fine-tuning and PyTorch research",
        tech_stack='["Python", "PyTorch", "LLM", "NLP"]',
        salary_min=1400,
        salary_max=1600,
        job_type="internship",
        remote_option="hybrid"
    )
    
    job2 = Job(
        title="AI Research Intern",
        company="Rakuten",
        location="Paris, France",
        url="https://glassdoor.com/job/789012",
        source="glassdoor",
        description="Research lab with publication potential",
        tech_stack='["Python", "TensorFlow", "Research"]',
        salary_min=1000,
        salary_max=1200,
        job_type="internship",
        remote_option="onsite"
    )
    
    # Insert jobs
    job1_id = JobRepository.insert(job1)
    job2_id = JobRepository.insert(job2)
    
    print(f"✅ Inserted job 1: ID {job1_id}")
    print(f"✅ Inserted job 2: ID {job2_id}")
    
    # Test deduplication
    print("\n3. Testing deduplication...")
    duplicate_id = JobRepository.insert(job1)  # Same URL as job1
    print(f"   Duplicate insert result: {duplicate_id} (should be None)")
    
    # Check if job exists
    exists = JobRepository.exists(job1.url)
    print(f"   Job exists check: {exists}")
    
    # Retrieve jobs
    print("\n4. Retrieving jobs...")
    all_jobs = JobRepository.get_all()
    print(f"   Total jobs: {len(all_jobs)}")
    
    retrieved_job = JobRepository.get_by_id(job1_id)
    if retrieved_job:
        print(f"   Retrieved: {retrieved_job.title} at {retrieved_job.company}")
    
    # Search jobs
    print("\n5. Searching jobs...")
    ml_jobs = JobRepository.search(keyword="Machine Learning")
    print(f"   'Machine Learning' search results: {len(ml_jobs)}")
    
    # Create scores
    print("\n6. Scoring jobs...")
    
    score1 = Score(
        job_id=job1_id,
        tech_match=85.0,
        learning_opportunity=90.0,
        company_quality=80.0,
        practical_factors=75.0
    )
    score1.calculate_total()  # Calculate weighted total
    
    score2 = Score(
        job_id=job2_id,
        tech_match=75.0,
        learning_opportunity=95.0,
        company_quality=70.0,
        practical_factors=65.0
    )
    score2.calculate_total()
    
    ScoreRepository.insert(score1)
    ScoreRepository.insert(score2)
    
    print(f"   Job 1 score: {score1.total_score}/100")
    print(f"   Job 2 score: {score2.total_score}/100")
    
    # Get top scored jobs
    print("\n7. Top scored jobs...")
    top_jobs = ScoreRepository.get_top_scored(limit=5)
    
    for idx, (score, job) in enumerate(top_jobs, 1):
        print(f"   [{idx}] {score.total_score:.1f}/100 - {job.title} at {job.company}")
    
    # Create application
    print("\n8. Tracking application...")
    
    app = Application(
        job_id=job1_id,
        status="applied",
        applied_date=datetime.now(),
        notes="Strong match, sent customized cover letter"
    )
    
    app_id = ApplicationRepository.insert(app)
    print(f"   Created application ID {app_id}")
    
    # Update application status
    ApplicationRepository.update_status(
        job_id=job1_id,
        status="interview",
        notes="Phone interview scheduled for next week"
    )
    print("   Updated application status to 'interview'")
    
    # Get application by status
    interviews = ApplicationRepository.get_by_status("interview")
    print(f"   Total interviews: {len(interviews)}")
    
    # Statistics
    print("\n9. Database statistics...")
    total_jobs = JobRepository.count()
    glassdoor_jobs = JobRepository.count(source="glassdoor")
    
    print(f"   Total jobs: {total_jobs}")
    print(f"   Glassdoor jobs: {glassdoor_jobs}")
    
    print("\n" + "=" * 60)
    print("✅ Demo completed successfully!")
    print("=" * 60)
    print(f"\nDatabase location: data/joblass.db")
    print("You can inspect it with: sqlite3 data/joblass.db")


if __name__ == "__main__":
    demo_database()
