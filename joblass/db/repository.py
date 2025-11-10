"""
Database repository layer for CRUD operations with SQLModel
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from joblass.db.engine import get_session
from joblass.db.models import Application, Company, Job, Score, SearchSession
from joblass.utils.logger import setup_logger

logger = setup_logger(__name__)


class JobRepository:
    """Repository for job operations with SQLModel"""

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
            with get_session() as session:
                session.add(job)
                session.commit()
                session.refresh(job)
                logger.info(
                    f"✓ Inserted job: {job.title} at {job.company} (ID: {job.id}, URL: {job.url})"
                )
                return job.id
        except IntegrityError as e:
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
            with get_session() as session:
                return session.get(Job, job_id)
        except Exception as e:
            logger.error(f"Failed to fetch job {job_id}: {e}", exc_info=True)
            return None

    @staticmethod
    def get_by_url(url: str) -> Optional[Job]:
        """Get job by URL (primary deduplication method)"""
        try:
            with get_session() as session:
                statement = select(Job).where(Job.url == url)
                return session.exec(statement).first()
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
            order_by: SQL ORDER BY clause (e.g., "scraped_date DESC")

        Returns:
            List of Job objects
        """
        try:
            with get_session() as session:
                statement = select(Job)

                if source:
                    statement = statement.where(Job.source == source)

                # Parse order_by string (simple version)
                if "DESC" in order_by:
                    field = order_by.replace(" DESC", "").strip()
                    statement = statement.order_by(col(getattr(Job, field)).desc())
                else:
                    field = order_by.replace(" ASC", "").strip()
                    statement = statement.order_by(col(getattr(Job, field)))

                if offset:
                    statement = statement.offset(offset)
                if limit:
                    statement = statement.limit(limit)

                return list(session.exec(statement).all())
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
            with get_session() as session:
                statement = select(Job)

                conditions = []
                if keyword:
                    conditions.append(
                        (col(Job.title).contains(keyword))
                        | (col(Job.description).contains(keyword))
                    )
                if company:
                    conditions.append(col(Job.company).contains(company))
                if location:
                    conditions.append(col(Job.location).contains(location))

                if conditions:
                    # Combine all conditions with AND
                    for condition in conditions:
                        statement = statement.where(condition)

                statement = statement.order_by(col(Job.scraped_date).desc())
                return list(session.exec(statement).all())
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
            with get_session() as session:
                job.updated_at = datetime.now()
                session.add(job)
                session.commit()
                logger.info(f"Updated job ID {job.id}")
                return True
        except Exception as e:
            logger.error(f"Failed to update job: {e}", exc_info=True)
            return False

    @staticmethod
    def delete(job_id: int) -> bool:
        """Delete job by ID"""
        try:
            with get_session() as session:
                job = session.get(Job, job_id)
                if job:
                    session.delete(job)
                    session.commit()
                    logger.info(f"Deleted job ID {job_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to delete job: {e}", exc_info=True)
            return False

    @staticmethod
    def count(source: Optional[str] = None) -> int:
        """Count total jobs, optionally filtered by source"""
        try:
            with get_session() as session:
                statement = select(Job)
                if source:
                    statement = statement.where(Job.source == source)

                # Use count() - SQLModel doesn't have a direct count, so we get all and len
                results = session.exec(statement).all()
                return len(results)
        except Exception as e:
            logger.error(f"Failed to count jobs: {e}", exc_info=True)
            return 0


class ApplicationRepository:
    """Repository for application tracking"""

    @staticmethod
    def insert(application: Application) -> Optional[int]:
        """Insert new application"""
        try:
            with get_session() as session:
                session.add(application)
                session.commit()
                session.refresh(application)
                logger.info(
                    f"Created application for job ID {application.job_id} (ID: {application.id})"
                )
                return application.id
        except Exception as e:
            logger.error(f"Failed to insert application: {e}", exc_info=True)
            return None

    @staticmethod
    def get_by_job_id(job_id: int) -> Optional[Application]:
        """Get application for a specific job"""
        try:
            with get_session() as session:
                statement = select(Application).where(Application.job_id == job_id)
                return session.exec(statement).first()
        except Exception as e:
            logger.error(f"Failed to fetch application: {e}", exc_info=True)
            return None

    @staticmethod
    def get_by_status(status: str) -> List[Application]:
        """Get all applications with specific status"""
        try:
            with get_session() as session:
                statement = (
                    select(Application)
                    .where(Application.status == status)
                    .order_by(col(Application.last_updated).desc())
                )
                return list(session.exec(statement).all())
        except Exception as e:
            logger.error(f"Failed to fetch applications: {e}", exc_info=True)
            return []

    @staticmethod
    def update_status(job_id: int, status: str, notes: Optional[str] = None) -> bool:
        """Update application status"""
        try:
            with get_session() as session:
                statement = select(Application).where(Application.job_id == job_id)
                app = session.exec(statement).first()
                if app:
                    app.status = status
                    app.last_updated = datetime.now()
                    if notes:
                        app.notes = notes
                    session.add(app)
                    session.commit()
                    logger.info(
                        f"Updated application status for job {job_id} to {status}"
                    )
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to update application status: {e}", exc_info=True)
            return False


class ScoreRepository:
    """Repository for job scoring"""

    @staticmethod
    def insert(score: Score) -> Optional[int]:
        """Insert job score"""
        try:
            with get_session() as session:
                session.add(score)
                session.commit()
                session.refresh(score)
                logger.info(
                    f"Inserted score for job {score.job_id}: {score.total_score}/100"
                )
                return score.id
        except IntegrityError:
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
            with get_session() as session:
                statement = select(Score).where(Score.job_id == job_id)
                return session.exec(statement).first()
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
            with get_session() as session:
                statement = (
                    select(Score, Job)
                    .join(Job, Score.job_id == Job.id)
                    .where(Score.total_score >= min_score)
                    .order_by(col(Score.total_score).desc())
                    .limit(limit)
                )
                results = session.exec(statement).all()
                return list(results)
        except Exception as e:
            logger.error(f"Failed to fetch top scored jobs: {e}", exc_info=True)
            return []

    @staticmethod
    def update(score: Score) -> Optional[int]:
        """Update existing score"""
        try:
            with get_session() as session:
                statement = select(Score).where(Score.job_id == score.job_id)
                existing = session.exec(statement).first()
                if existing:
                    existing.tech_match = score.tech_match
                    existing.learning_opportunity = score.learning_opportunity
                    existing.company_quality = score.company_quality
                    existing.practical_factors = score.practical_factors
                    existing.total_score = score.total_score
                    existing.penalties = score.penalties
                    existing.bonuses = score.bonuses
                    existing.llm_analysis = score.llm_analysis
                    existing.red_flags = score.red_flags
                    existing.updated_at = datetime.now()
                    session.add(existing)
                    session.commit()
                    logger.info(f"Updated score for job {score.job_id}")
                    return score.job_id
                return None
        except Exception as e:
            logger.error(f"Failed to update score: {e}", exc_info=True)
            return None


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
            # Convert SearchCriteria object to dict if needed
            from joblass.db.models import SearchCriteria

            if isinstance(session.search_criteria, SearchCriteria):
                session.search_criteria = session.search_criteria.model_dump(
                    exclude_none=True
                )

            with get_session() as db_session:
                db_session.add(session)
                db_session.commit()
                db_session.refresh(session)
                logger.info(
                    f"Created search session (ID: {session.id}): "
                    f"source={session.source}, status={session.status}"
                )
                return session.id
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
            with get_session() as db_session:
                session.updated_at = datetime.now()
                db_session.add(session)
                db_session.commit()
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
            with get_session() as db_session:
                return db_session.get(SearchSession, session_id)
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
            with get_session() as db_session:
                statement = select(SearchSession)

                if status:
                    statement = statement.where(SearchSession.status == status)

                # Parse order_by
                if " " in order_by:
                    field_name, direction = order_by.split()
                    field = getattr(SearchSession, field_name)
                    if direction.upper() == "DESC":
                        statement = statement.order_by(col(field).desc())
                    else:
                        statement = statement.order_by(col(field))
                else:
                    field = getattr(SearchSession, order_by)
                    statement = statement.order_by(col(field))

                statement = statement.offset(offset)
                if limit:
                    statement = statement.limit(limit)

                return list(db_session.exec(statement).all())
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
            with get_session() as db_session:
                statement = (
                    select(Job)
                    .where(Job.session_id == session_id)
                    .order_by(col(Job.scraped_date).desc())
                )
                return list(db_session.exec(statement).all())
        except Exception as e:
            logger.error(
                f"Failed to fetch jobs for session {session_id}: {e}", exc_info=True
            )
            return []

    @staticmethod
    def count(status: Optional[str] = None) -> int:
        """Count total sessions, optionally filtered by status"""
        try:
            with get_session() as db_session:
                statement = select(SearchSession)
                if status:
                    statement = statement.where(SearchSession.status == status)

                results = db_session.exec(statement).all()
                return len(results)
        except Exception as e:
            logger.error(f"Failed to count sessions: {e}", exc_info=True)
            return 0

    @staticmethod
    def delete(session_id: int) -> bool:
        """Delete search session by ID (jobs will have session_id set to NULL)"""
        try:
            with get_session() as db_session:
                session = db_session.get(SearchSession, session_id)
                if session:
                    db_session.delete(session)
                    db_session.commit()
                    logger.info(f"Deleted search session ID {session_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to delete session: {e}", exc_info=True)
            return False


class CompanyRepository:
    """Repository for company operations with SQLModel"""

    @staticmethod
    def upsert(company: Company) -> Optional[int]:  # noqa: C901
        """
        Insert or get existing company by name (case-insensitive).
        Updates page_source to 'merged' if inserting profile data over job_posting data.

        Args:
            company: Company object to insert or update

        Returns:
            Company ID (existing or newly inserted)

        Note:
            - Unique by name (case-insensitive)
            - If company exists with 'job_posting' source and new is 'company_profile',
              merges data and updates page_source to 'merged'
        """
        try:
            with get_session() as session:
                # Check if company exists (case-insensitive)
                statement = select(Company).where(col(Company.name).ilike(company.name))
                existing = session.exec(statement).first()

                if existing:
                    # Company exists - decide whether to update or just return ID
                    should_update = False

                    # Merge logic: job_posting -> company_profile = merged
                    if (
                        existing.page_source == "job_posting"
                        and company.page_source == "company_profile"
                    ):
                        # Merge company profile data into job posting data
                        if company.overview:
                            existing.overview = company.overview
                        if company.evaluations:
                            existing.evaluations = company.evaluations
                        if company.profile_url and not existing.profile_url:
                            existing.profile_url = company.profile_url

                        existing.page_source = "merged"
                        existing.updated_at = datetime.now()
                        should_update = True

                    elif (
                        existing.page_source == "company_profile"
                        and company.page_source == "job_posting"
                    ):
                        # Don't downgrade from profile to job_posting
                        # But update job_posting fields if missing
                        if company.reviews_summary and not existing.reviews_summary:
                            existing.reviews_summary = company.reviews_summary
                        if company.salary_estimates and not existing.salary_estimates:
                            existing.salary_estimates = company.salary_estimates
                        existing.updated_at = datetime.now()
                        should_update = True

                    if should_update:
                        session.add(existing)
                        session.commit()
                        session.refresh(existing)
                        logger.info(
                            f"✓ Updated company: {existing.name} (ID: {existing.id}, source: {existing.page_source})"
                        )

                    logger.debug(
                        f"Company already exists: {existing.name} (ID: {existing.id})"
                    )
                    return existing.id

                # Insert new company
                session.add(company)
                session.commit()
                session.refresh(company)
                logger.info(
                    f"✓ Inserted company: {company.name} (ID: {company.id}, source: {company.page_source})"
                )
                return company.id

        except IntegrityError as e:
            # Shouldn't happen with our check, but handle race conditions
            logger.warning(f"Company already exists (race condition): {company.name}")
            logger.debug(f"IntegrityError details: {e}")
            # Retry: fetch existing company ID
            try:
                with get_session() as session:
                    statement = select(Company).where(
                        col(Company.name).ilike(company.name)
                    )
                    existing = session.exec(statement).first()
                    return existing.id if existing else None
            except Exception as retry_e:
                logger.error(f"Failed to fetch company on retry: {retry_e}")
                return None
        except Exception as e:
            logger.error(
                f"Database error upserting company {company.name}: {e}", exc_info=True
            )
            raise

    @staticmethod
    def get_by_id(company_id: int) -> Optional[Company]:
        """Get company by ID"""
        try:
            with get_session() as session:
                return session.get(Company, company_id)
        except Exception as e:
            logger.error(f"Failed to fetch company {company_id}: {e}", exc_info=True)
            return None

    @staticmethod
    def get_by_name(name: str, case_sensitive: bool = False) -> Optional[Company]:
        """
        Get company by name

        Args:
            name: Company name
            case_sensitive: Whether to match case-sensitively (default: False)

        Returns:
            Company object or None
        """
        try:
            with get_session() as session:
                if case_sensitive:
                    statement = select(Company).where(Company.name == name)
                else:
                    statement = select(Company).where(col(Company.name).ilike(name))
                return session.exec(statement).first()
        except Exception as e:
            logger.error(f"Failed to fetch company by name: {e}", exc_info=True)
            return None

    @staticmethod
    def get_all(
        limit: Optional[int] = None,
        offset: int = 0,
        page_source: Optional[str] = None,
    ) -> List[Company]:
        """
        Get all companies with optional filtering

        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            page_source: Filter by page_source ('job_posting', 'company_profile', 'merged')

        Returns:
            List of Company objects
        """
        try:
            with get_session() as session:
                statement = select(Company).order_by(col(Company.name))

                if page_source:
                    statement = statement.where(Company.page_source == page_source)

                if offset:
                    statement = statement.offset(offset)
                if limit:
                    statement = statement.limit(limit)

                return list(session.exec(statement).all())
        except Exception as e:
            logger.error(f"Failed to fetch companies: {e}", exc_info=True)
            return []
