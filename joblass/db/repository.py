"""
Database repository layer for CRUD operations
"""

import sqlite3
from datetime import datetime
from typing import List, Optional

from joblass.db.connection import get_db_cursor
from joblass.db.models import Application, Job, Score, SearchSession
from joblass.utils.logger import setup_logger

logger = setup_logger(__name__)


class JobRepository:
    """Repository for job operations"""

    @staticmethod
    def insert(job: Job) -> Optional[int]:
        """
        Insert a new job into database with URL-based deduplication.

        Args:
            job: Job object to insert

        Returns:
            Job ID if successful, None if duplicate URL exists

        Raises:
            Exception: For database errors other than duplicates (e.g., connection errors)

        Note:
            Duplicates (IntegrityError) return None with a warning log.
            Other database errors are raised to the caller for proper handling.
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO jobs (
                        title, company, location, url, source,
                        description, tech_stack,
                        salary_min, salary_max, salary_median, salary_currency,
                        posted_date, scraped_date, job_age, job_type, remote_option,
                        is_easy_apply, job_external_id,
                        company_size, company_industry, company_sector,
                        company_founded, company_type, company_revenue,
                        reviews_data, session_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        job.title,
                        job.company,
                        job.location,
                        job.url,
                        job.source,
                        job.description,
                        job.tech_stack,
                        job.salary_min,
                        job.salary_max,
                        job.salary_median,
                        job.salary_currency,
                        job.posted_date,
                        job.scraped_date,
                        job.job_age,
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
                        job.session_id,
                    ),
                )
                job_id = cursor.lastrowid
                logger.info(
                    f"✓ Inserted job: {job.title} at {job.company} (ID: {job_id}, URL: {job.url})"
                )
                return job_id
        except sqlite3.IntegrityError as e:
            # Duplicate URL - this is expected during scraping, return None gracefully
            logger.warning(
                f"Job already exists (duplicate URL): {job.url} - {job.title} at {job.company}"
            )
            logger.debug(f"IntegrityError details: {e}")
            return None
        except Exception as e:
            # Unexpected database error - log and re-raise for caller to handle
            logger.error(
                f"Database error inserting job {job.title} at {job.company}: {e}",
                exc_info=True,
            )
            raise  # Re-raise the exception

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
        """Get job by URL (primary deduplication method)"""
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
    def exists(url: str | None = None, job: Job | None = None) -> bool:
        """
        Check if job exists by URL

        Args:
            url: Job URL (primary method)
            job: Job object (extracts URL for checking)

        Returns:
            True if job exists in database
        """
        # Priority 1: Use URL directly
        if url:
            return JobRepository.get_by_url(url) is not None

        # Priority 2: Extract URL from job object
        if job:
            return JobRepository.get_by_url(job.url) is not None

        logger.warning("exists() called without url or job - returning False")
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
                        title = ?, company = ?, location = ?, url = ?,
                        description = ?, tech_stack = ?,
                        salary_min = ?, salary_max = ?, salary_median = ?, salary_currency = ?,
                        posted_date = ?, job_age = ?, job_type = ?, remote_option = ?,
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
                        job.description,
                        job.tech_stack,
                        job.salary_min,
                        job.salary_max,
                        job.salary_median,
                        job.salary_currency,
                        job.posted_date,
                        job.job_age,
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
                        job_id, status, application_method, applied_date, last_updated,
                        cover_letter_path, notes, interview_date, interview_notes,
                        rejection_date, rejection_reason, offer_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        application.job_id,
                        application.status,
                        application.application_method,
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


class SearchSessionRepository:
    """Repository for search session tracking"""

    @staticmethod
    def insert(session: SearchSession) -> Optional[int]:
        """
        Create new search session

        Args:
            session: SearchSession object to insert

        Returns:
            Session ID if successful, None otherwise
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO search_sessions (
                        search_criteria, source, status,
                        jobs_found, jobs_scraped, jobs_saved, jobs_skipped,
                        error_message, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        session.search_criteria.to_json(),
                        session.source,
                        session.status,
                        session.jobs_found,
                        session.jobs_scraped,
                        session.jobs_saved,
                        session.jobs_skipped,
                        session.error_message,
                        session.created_at,
                        session.updated_at,
                    ),
                )
                session_id = cursor.lastrowid
                logger.info(
                    f"Created search session (ID: {session_id}): "
                    f"{session.search_criteria.job_title} in {session.search_criteria.location}"
                )
                return session_id
        except Exception as e:
            logger.error(f"Failed to insert search session: {e}", exc_info=True)
            return None

    @staticmethod
    def update(session: SearchSession) -> bool:
        """
        Update existing search session

        Args:
            session: SearchSession object with updated data

        Returns:
            True if successful, False otherwise
        """
        if not session.id:
            logger.error("Cannot update session without ID")
            return False

        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE search_sessions SET
                        status = ?,
                        jobs_found = ?,
                        jobs_scraped = ?,
                        jobs_saved = ?,
                        jobs_skipped = ?,
                        error_message = ?,
                        updated_at = ?
                    WHERE id = ?
                """,
                    (
                        session.status,
                        session.jobs_found,
                        session.jobs_scraped,
                        session.jobs_saved,
                        session.jobs_skipped,
                        session.error_message,
                        session.updated_at,
                        session.id,
                    ),
                )
                logger.info(
                    f"Updated search session {session.id}: "
                    f"status={session.status}, saved={session.jobs_saved}/{session.jobs_scraped}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to update search session: {e}", exc_info=True)
            return False

    @staticmethod
    def get_by_id(session_id: int) -> Optional[SearchSession]:
        """Get search session by ID"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM search_sessions WHERE id = ?", (session_id,)
                )
                row = cursor.fetchone()
                if row:
                    return SearchSessionRepository._row_to_session(row)
                return None
        except Exception as e:
            logger.error(f"Failed to fetch session {session_id}: {e}", exc_info=True)
            return None

    @staticmethod
    def get_all(
        limit: Optional[int] = None,
        offset: int = 0,
        status: Optional[str] = None,
        order_by: str = "created_at DESC",
    ) -> List[SearchSession]:
        """
        Get all search sessions with optional filtering

        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            status: Filter by status ('in_progress', 'completed', 'failed')
            order_by: SQL ORDER BY clause

        Returns:
            List of SearchSession objects
        """
        try:
            query = "SELECT * FROM search_sessions"
            params = []

            if status:
                query += " WHERE status = ?"
                params.append(status)

            query += f" ORDER BY {order_by}"

            if limit:
                query += " LIMIT ? OFFSET ?"
                params.extend([str(limit), str(offset)])

            with get_db_cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [SearchSessionRepository._row_to_session(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch sessions: {e}", exc_info=True)
            return []

    @staticmethod
    def get_jobs_by_session(session_id: int) -> List[Job]:
        """
        Get all jobs from a specific search session

        Args:
            session_id: Search session ID

        Returns:
            List of Job objects from that session
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM jobs WHERE session_id = ? ORDER BY scraped_date DESC",
                    (session_id,),
                )
                rows = cursor.fetchall()
                return [JobRepository._row_to_job(row) for row in rows]
        except Exception as e:
            logger.error(
                f"Failed to fetch jobs for session {session_id}: {e}", exc_info=True
            )
            return []

    @staticmethod
    def count(status: Optional[str] = None) -> int:
        """Count total sessions, optionally filtered by status"""
        try:
            query = "SELECT COUNT(*) FROM search_sessions"
            params = []

            if status:
                query += " WHERE status = ?"
                params.append(status)

            with get_db_cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to count sessions: {e}", exc_info=True)
            return 0

    @staticmethod
    def delete(session_id: int) -> bool:
        """Delete search session by ID (jobs will have session_id set to NULL)"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    "DELETE FROM search_sessions WHERE id = ?", (session_id,)
                )
                logger.info(f"Deleted search session ID {session_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete session: {e}", exc_info=True)
            return False

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> SearchSession:
        """Convert database row to SearchSession object using Pydantic"""
        from joblass.db.models import SearchCriteria

        data = dict(row)

        # Parse JSON search criteria
        if data.get("search_criteria"):
            data["search_criteria"] = SearchCriteria.from_json(data["search_criteria"])

        # Parse datetime fields
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])

        # Pydantic handles validation and type conversion
        return SearchSession.model_validate(data)
