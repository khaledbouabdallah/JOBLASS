"""
Database repository layer for CRUD operations
"""

import sqlite3
from datetime import datetime
from typing import List, Optional

from joblass.db.connection import get_db_cursor
from joblass.db.models import Application, Job, Score
from joblass.utils.logger import setup_logger

logger = setup_logger(__name__)


class JobRepository:
    """Repository for job operations"""

    @staticmethod
    def insert(job: Job) -> Optional[int]:
        """
        Insert a new job into database

        Args:
            job: Job object to insert

        Returns:
            Job ID if successful, None otherwise
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO jobs (
                        title, company, location, url, job_hash, source,
                        description, tech_stack, verified_skills, required_skills,
                        salary_min, salary_max, salary_median, salary_currency,
                        posted_date, scraped_date, job_type, remote_option,
                        is_easy_apply, job_external_id,
                        company_size, company_industry, company_sector,
                        company_founded, company_type, company_revenue,
                        reviews_data, raw_html
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        job.title,
                        job.company,
                        job.location,
                        job.url,
                        job.job_hash,
                        job.source,
                        job.description,
                        job.tech_stack,
                        job.verified_skills,
                        job.required_skills,
                        job.salary_min,
                        job.salary_max,
                        job.salary_median,
                        job.salary_currency,
                        job.posted_date,
                        job.scraped_date,
                        job.job_type,
                        job.remote_option,
                        job.is_easy_apply,
                        job.job_external_id,
                        job.company_size,
                        job.company_industry,
                        job.company_sector,
                        job.company_founded,
                        job.company_type,
                        job.company_revenue,
                        job.reviews_data,
                        job.raw_html,
                    ),
                )
                job_id = cursor.lastrowid
                logger.info(
                    f"Inserted job: {job.title} at {job.company} (ID: {job_id}, hash: {job.job_hash})"
                )
                return job_id
        except sqlite3.IntegrityError:
            logger.warning(
                f"Job already exists (duplicate hash): {job.job_hash} - {job.title} at {job.company}"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to insert job: {e}", exc_info=True)
            return None

    @staticmethod
    def get_by_id(job_id: int) -> Optional[Job]:
        """Get job by ID"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
                row = cursor.fetchone()
                if row:
                    return JobRepository._row_to_job(row)
                return None
        except Exception as e:
            logger.error(f"Failed to fetch job {job_id}: {e}", exc_info=True)
            return None

    @staticmethod
    def get_by_url(url: str) -> Optional[Job]:
        """Get job by URL (for backward compatibility)"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT * FROM jobs WHERE url = ?", (url,))
                row = cursor.fetchone()
                if row:
                    return JobRepository._row_to_job(row)
                return None
        except Exception as e:
            logger.error(f"Failed to fetch job by URL: {e}", exc_info=True)
            return None

    @staticmethod
    def get_by_hash(job_hash: str) -> Optional[Job]:
        """Get job by hash (primary deduplication method)"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT * FROM jobs WHERE job_hash = ?", (job_hash,))
                row = cursor.fetchone()
                if row:
                    return JobRepository._row_to_job(row)
                return None
        except Exception as e:
            logger.error(f"Failed to fetch job by hash: {e}", exc_info=True)
            return None

    @staticmethod
    def exists(
        url: str | None = None, job: Job | None = None, job_hash: str | None = None
    ) -> bool:
        """
        Check if job exists using multiple strategies

        Priority order:
        1. job_hash (if provided or can be generated from job)
        2. job object (generates hash)
        3. URL (legacy fallback)

        Args:
            url: Job URL (legacy method)
            job: Job object (generates hash for checking)
            job_hash: Pre-computed job hash

        Returns:
            True if job exists in database
        """
        # Priority 1: Use provided hash
        if job_hash:
            return JobRepository.get_by_hash(job_hash) is not None

        # Priority 2: Generate hash from job object
        if job:
            generated_hash = job.generate_hash()
            return JobRepository.get_by_hash(generated_hash) is not None

        # Priority 3: Legacy URL-based check (least reliable)
        if url:
            return JobRepository.get_by_url(url) is not None

        logger.warning(
            "exists() called without url, job, or job_hash - returning False"
        )
        return False

    @staticmethod
    def get_all(
        limit: Optional[int] = None,
        offset: int = 0,
        source: Optional[str] = None,
        order_by: str = "scraped_date DESC",
    ) -> List[Job]:
        """
        Get all jobs with optional filtering

        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            source: Filter by source (e.g., 'glassdoor')
            order_by: SQL ORDER BY clause

        Returns:
            List of Job objects
        """
        try:
            query = "SELECT * FROM jobs"
            params = []

            if source:
                query += " WHERE source = ?"
                params.append(source)

            query += f" ORDER BY {order_by}"

            if limit:
                query += " LIMIT ? OFFSET ?"
                params.extend([str(limit), str(offset)])

            with get_db_cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [JobRepository._row_to_job(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch jobs: {e}", exc_info=True)
            return []

    @staticmethod
    def search(
        keyword: Optional[str] = None,
        company: Optional[str] = None,
        location: Optional[str] = None,
    ) -> List[Job]:
        """
        Search jobs by keyword, company, or location

        Args:
            keyword: Search in title and description
            company: Filter by company name
            location: Filter by location

        Returns:
            List of matching Job objects
        """
        try:
            conditions = []
            params = []

            if keyword:
                conditions.append("(title LIKE ? OR description LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            if company:
                conditions.append("company LIKE ?")
                params.append(f"%{company}%")

            if location:
                conditions.append("location LIKE ?")
                params.append(f"%{location}%")

            query = "SELECT * FROM jobs"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY scraped_date DESC"

            with get_db_cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [JobRepository._row_to_job(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to search jobs: {e}", exc_info=True)
            return []

    @staticmethod
    def update(job: Job) -> bool:
        """Update existing job"""
        if not job.id:
            logger.error("Cannot update job without ID")
            return False

        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE jobs SET
                        title = ?, company = ?, location = ?, url = ?, job_hash = ?,
                        description = ?, tech_stack = ?, verified_skills = ?, required_skills = ?,
                        salary_min = ?, salary_max = ?, salary_median = ?, salary_currency = ?,
                        posted_date = ?, job_type = ?, remote_option = ?,
                        is_easy_apply = ?, job_external_id = ?,
                        company_size = ?, company_industry = ?, company_sector = ?,
                        company_founded = ?, company_type = ?, company_revenue = ?,
                        reviews_data = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (
                        job.title,
                        job.company,
                        job.location,
                        job.url,
                        job.job_hash,
                        job.description,
                        job.tech_stack,
                        job.verified_skills,
                        job.required_skills,
                        job.salary_min,
                        job.salary_max,
                        job.salary_median,
                        job.salary_currency,
                        job.posted_date,
                        job.job_type,
                        job.remote_option,
                        job.is_easy_apply,
                        job.job_external_id,
                        job.company_size,
                        job.company_industry,
                        job.company_sector,
                        job.company_founded,
                        job.company_type,
                        job.company_revenue,
                        job.reviews_data,
                        job.id,
                    ),
                )
                logger.info(f"Updated job ID {job.id}")
                return True
        except Exception as e:
            logger.error(f"Failed to update job: {e}", exc_info=True)
            return False

    @staticmethod
    def delete(job_id: int) -> bool:
        """Delete job by ID"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
                logger.info(f"Deleted job ID {job_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete job: {e}", exc_info=True)
            return False

    @staticmethod
    def count(source: Optional[str] = None) -> int:
        """Count total jobs, optionally filtered by source"""
        try:
            query = "SELECT COUNT(*) FROM jobs"
            params = []

            if source:
                query += " WHERE source = ?"
                params.append(source)

            with get_db_cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to count jobs: {e}", exc_info=True)
            return 0

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        """Convert database row to Job object using Pydantic"""
        # Convert row to dict
        data = dict(row)

        # Parse datetime fields
        if data.get("posted_date"):
            data["posted_date"] = datetime.fromisoformat(data["posted_date"])
        if data.get("scraped_date"):
            data["scraped_date"] = datetime.fromisoformat(data["scraped_date"])

        # Pydantic handles validation and type conversion
        return Job.model_validate(data)


class ApplicationRepository:
    """Repository for application tracking"""

    @staticmethod
    def insert(application: Application) -> Optional[int]:
        """Insert new application"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO applications (
                        job_id, status, applied_date, last_updated,
                        cover_letter_path, notes, interview_date, interview_notes,
                        rejection_date, rejection_reason, offer_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        application.job_id,
                        application.status,
                        application.applied_date,
                        application.last_updated,
                        application.cover_letter_path,
                        application.notes,
                        application.interview_date,
                        application.interview_notes,
                        application.rejection_date,
                        application.rejection_reason,
                        application.offer_date,
                    ),
                )
                app_id = cursor.lastrowid
                logger.info(
                    f"Created application for job ID {application.job_id} (ID: {app_id})"
                )
                return app_id
        except Exception as e:
            logger.error(f"Failed to insert application: {e}", exc_info=True)
            return None

    @staticmethod
    def get_by_job_id(job_id: int) -> Optional[Application]:
        """Get application for a specific job"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()
                if row:
                    return ApplicationRepository._row_to_application(row)
                return None
        except Exception as e:
            logger.error(f"Failed to fetch application: {e}", exc_info=True)
            return None

    @staticmethod
    def get_by_status(status: str) -> List[Application]:
        """Get all applications with specific status"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM applications WHERE status = ? ORDER BY last_updated DESC",
                    (status,),
                )
                rows = cursor.fetchall()
                return [ApplicationRepository._row_to_application(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch applications: {e}", exc_info=True)
            return []

    @staticmethod
    def update_status(job_id: int, status: str, notes: Optional[str] = None) -> bool:
        """Update application status"""
        try:
            with get_db_cursor() as cursor:
                update_fields = ["status = ?", "last_updated = ?"]
                params = [status, datetime.now()]

                if notes:
                    update_fields.append("notes = ?")
                    params.append(notes)

                params.append(job_id)

                cursor.execute(
                    f"UPDATE applications SET {', '.join(update_fields)} WHERE job_id = ?",
                    params,
                )
                logger.info(f"Updated application status for job {job_id} to {status}")
                return True
        except Exception as e:
            logger.error(f"Failed to update application status: {e}", exc_info=True)
            return False

    @staticmethod
    def _row_to_application(row: sqlite3.Row) -> Application:
        """Convert database row to Application object using Pydantic"""
        # Convert row to dict
        data = dict(row)

        # Parse datetime fields
        for field in [
            "applied_date",
            "last_updated",
            "interview_date",
            "rejection_date",
            "offer_date",
        ]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        # Pydantic handles validation and type conversion
        return Application.model_validate(data)


class ScoreRepository:
    """Repository for job scoring"""

    @staticmethod
    def insert(score: Score) -> Optional[int]:
        """Insert job score"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO scores (
                        job_id, tech_match, learning_opportunity,
                        company_quality, practical_factors, total_score,
                        penalties, bonuses, scored_date, llm_analysis, red_flags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        score.job_id,
                        score.tech_match,
                        score.learning_opportunity,
                        score.company_quality,
                        score.practical_factors,
                        score.total_score,
                        score.penalties,
                        score.bonuses,
                        score.scored_date,
                        score.llm_analysis,
                        score.red_flags,
                    ),
                )
                score_id = cursor.lastrowid
                logger.info(
                    f"Inserted score for job {score.job_id}: {score.total_score}/100"
                )
                return score_id
        except sqlite3.IntegrityError:
            logger.warning(
                f"Score already exists for job {score.job_id}, updating instead"
            )
            return ScoreRepository.update(score)
        except Exception as e:
            logger.error(f"Failed to insert score: {e}", exc_info=True)
            return None

    @staticmethod
    def get_by_job_id(job_id: int) -> Optional[Score]:
        """Get score for a specific job"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT * FROM scores WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()
                if row:
                    return ScoreRepository._row_to_score(row)
                return None
        except Exception as e:
            logger.error(f"Failed to fetch score: {e}", exc_info=True)
            return None

    @staticmethod
    def get_top_scored(
        limit: int = 10, min_score: float = 0.0
    ) -> List[tuple[Score, Job]]:
        """
        Get top scored jobs

        Args:
            limit: Maximum number of results
            min_score: Minimum score threshold

        Returns:
            List of (Score, Job) tuples ordered by total_score DESC
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT s.*, j.*
                    FROM scores s
                    JOIN jobs j ON s.job_id = j.id
                    WHERE s.total_score >= ?
                    ORDER BY s.total_score DESC
                    LIMIT ?
                """,
                    (min_score, limit),
                )

                results = []
                for row in cursor.fetchall():
                    # Extract score fields
                    score = Score(
                        id=row["id"],
                        job_id=row["job_id"],
                        tech_match=row["tech_match"],
                        learning_opportunity=row["learning_opportunity"],
                        company_quality=row["company_quality"],
                        practical_factors=row["practical_factors"],
                        total_score=row["total_score"],
                        penalties=row["penalties"],
                        bonuses=row["bonuses"],
                        scored_date=datetime.fromisoformat(row["scored_date"]),
                        llm_analysis=row["llm_analysis"],
                        red_flags=row["red_flags"],
                    )

                    # Extract job fields (skip first few columns that are score fields)
                    job = JobRepository._row_to_job(row)

                    results.append((score, job))

                return results
        except Exception as e:
            logger.error(f"Failed to fetch top scored jobs: {e}", exc_info=True)
            return []

    @staticmethod
    def update(score: Score) -> Optional[int]:
        """Update existing score"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE scores SET
                        tech_match = ?, learning_opportunity = ?,
                        company_quality = ?, practical_factors = ?, total_score = ?,
                        penalties = ?, bonuses = ?, llm_analysis = ?, red_flags = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ?
                """,
                    (
                        score.tech_match,
                        score.learning_opportunity,
                        score.company_quality,
                        score.practical_factors,
                        score.total_score,
                        score.penalties,
                        score.bonuses,
                        score.llm_analysis,
                        score.red_flags,
                        score.job_id,
                    ),
                )
                logger.info(f"Updated score for job {score.job_id}")
                return score.job_id
        except Exception as e:
            logger.error(f"Failed to update score: {e}", exc_info=True)
            return None

    @staticmethod
    def _row_to_score(row: sqlite3.Row) -> Score:
        """Convert database row to Score object using Pydantic"""
        # Convert row to dict
        data = dict(row)

        # Parse datetime fields
        if data.get("scored_date"):
            data["scored_date"] = datetime.fromisoformat(data["scored_date"])

        # Pydantic handles validation and type conversion
        return Score.model_validate(data)
