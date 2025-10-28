"""
Test hash-based job deduplication
"""

from joblass.db.models import Job
from joblass.db.repository import JobRepository


def test_job_hash_generation():
    """Test that job hash is generated correctly"""

    # Test 1: Hash based on external_id (most reliable)
    job1 = Job(
        title="ML Engineer",
        company="Google",
        location="Paris",
        url="https://glassdoor.com/job/123",
        source="glassdoor",
        job_external_id="GD-12345",
    )
    hash1 = job1.generate_hash()
    assert len(hash1) == 16, "Hash should be 16 characters"
    print(f"✓ Hash with external_id: {hash1}")

    # Test 2: Hash based on title + company + location (fallback)
    job2 = Job(
        title="ML Engineer",
        company="Google",
        location="Paris",
        url="https://glassdoor.com/job/456",
        source="glassdoor",
    )
    hash2 = job2.generate_hash()
    assert len(hash2) == 16, "Hash should be 16 characters"
    print(f"✓ Hash without external_id: {hash2}")

    # Test 3: Same job with different URL should have same hash
    job3 = Job(
        title="ML Engineer",
        company="Google",
        location="Paris",
        url="https://linkedin.com/job/789",  # Different URL
        source="glassdoor",
        job_external_id="GD-12345",  # Same external_id
    )
    hash3 = job3.generate_hash()
    assert hash1 == hash3, "Same job with different URL should have same hash"
    print(f"✓ Same job, different URL: {hash3} (matches hash1)")

    # Test 4: Case-insensitive and whitespace normalization
    job4 = Job(
        title="  ml  engineer  ",  # Extra whitespace
        company=" GOOGLE ",
        location="  paris  ",
        url="https://glassdoor.com/job/999",
        source="glassdoor",
    )
    hash4 = job4.generate_hash()
    assert hash2 == hash4, "Normalized titles should produce same hash"
    print(f"✓ Normalized whitespace: {hash4} (matches hash2)")

    # Test 5: Different jobs have different hashes
    job5 = Job(
        title="Data Scientist",  # Different title
        company="Google",
        location="Paris",
        url="https://glassdoor.com/job/555",
        source="glassdoor",
    )
    hash5 = job5.generate_hash()
    assert hash2 != hash5, "Different jobs should have different hashes"
    print(f"✓ Different job: {hash5} (different from hash2)")

    print("\n✅ All hash generation tests passed!")


def test_repository_deduplication():
    """Test that repository correctly detects duplicates"""
    from joblass.db import init_db

    # Initialize fresh database
    init_db(reset=True)

    # Test 1: Insert job with external_id
    job1 = Job(
        title="ML Engineer",
        company="Google",
        location="Paris",
        url="https://glassdoor.com/job/123",
        source="glassdoor",
        job_external_id="GD-12345",
        description="Great ML role",
    )

    job_id1 = JobRepository.insert(job1)
    assert job_id1 is not None, "First insert should succeed"
    print(f"✓ Inserted job 1 (ID: {job_id1})")

    # Test 2: Try to insert same job with different URL (should be detected as duplicate)
    job2 = Job(
        title="ML Engineer",
        company="Google",
        location="Paris",
        url="https://different-url.com/job/999",  # Different URL
        source="glassdoor",
        job_external_id="GD-12345",  # Same external_id
        description="Same job, different URL",
    )

    job_id2 = JobRepository.insert(job2)
    assert job_id2 is None, "Duplicate insert should fail"
    print("✓ Duplicate job rejected (same external_id)")

    # Test 3: Check exists() method with job object
    assert JobRepository.exists(job=job1), "exists(job=job1) should return True"
    print("✓ exists(job=job1) returns True")

    # Test 4: Check exists() method with hash
    hash1 = job1.generate_hash()
    assert JobRepository.exists(
        job_hash=hash1
    ), "exists(job_hash=...) should return True"
    print("✓ exists(job_hash=...) returns True")

    # Test 5: Insert job without external_id (uses title+company+location)
    job3 = Job(
        title="Data Scientist",
        company="Meta",
        location="London",
        url="https://glassdoor.com/job/333",
        source="glassdoor",
        description="Data science role",
    )

    job_id3 = JobRepository.insert(job3)
    assert job_id3 is not None, "Insert should succeed for new job"
    print(f"✓ Inserted job 3 (ID: {job_id3})")

    # Test 6: Try to insert same job with slightly different title (should be detected)
    job4 = Job(
        title="  data  scientist  ",  # Extra whitespace, different case
        company="Meta",
        location="London",
        url="https://linkedin.com/job/444",
        source="glassdoor",
    )

    job_id4 = JobRepository.insert(job4)
    assert job_id4 is None, "Duplicate insert should fail (normalized match)"
    print("✓ Duplicate job rejected (normalized title+company+location)")

    # Test 7: Count total jobs
    count = JobRepository.count()
    assert count == 2, f"Should have 2 jobs, got {count}"
    print(f"✓ Total jobs in DB: {count}")

    print("\n✅ All repository deduplication tests passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Job Hash Generation")
    print("=" * 60)
    test_job_hash_generation()

    print("\n" + "=" * 60)
    print("Testing Repository Deduplication")
    print("=" * 60)
    test_repository_deduplication()

    print("\n" + "=" * 60)
    print("🎉 All tests passed successfully!")
    print("=" * 60)
