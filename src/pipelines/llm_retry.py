"""
LLM Retry Helper — Robust retry logic for multiple LLM calls.

Wraps a bundle of LLM calls with exponential backoff and proper error handling.
"""

import asyncio
import time
from typing import TypeVar, Callable, Optional, Any
from configs.log_config import get_logger

logger = get_logger("llm_retry")

T = TypeVar("T")


async def retry_with_backoff(
    operation: Callable[[], Any],
    operation_name: str,
    max_retries: int = 3,
    base_delay: float = 2.0,
    timeout_per_attempt: float = 60.0,
) -> Any:
    """
    Retry an async operation with exponential backoff.
    
    Args:
        operation: Async function to execute
        operation_name: Name for logging
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        timeout_per_attempt: Timeout for each attempt in seconds
    
    Returns:
        Result of the operation
    
    Raises:
        Last exception encountered if all retries fail
    """
    last_error: Optional[Exception] = None
    
    for attempt in range(1, max_retries + 1):
        start_time = time.time()
        try:
            logger.info(
                "%s: attempt %d/%d",
                operation_name,
                attempt,
                max_retries,
            )
            
            result = await asyncio.wait_for(
                operation(),
                timeout=timeout_per_attempt,
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "%s: success in %dms (attempt %d)",
                operation_name,
                elapsed_ms,
                attempt,
            )
            
            return result
            
        except asyncio.TimeoutError:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                "%s: timeout after %dms (attempt %d/%d)",
                operation_name,
                elapsed_ms,
                attempt,
                max_retries,
            )
            last_error = asyncio.TimeoutError(
                f"{operation_name} timed out after {elapsed_ms}ms"
            )
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "%s: failed after %dms (attempt %d/%d): %s",
                operation_name,
                elapsed_ms,
                attempt,
                max_retries,
                str(e),
            )
            last_error = e
        
        # Exponential backoff before next retry
        if attempt < max_retries:
            delay = base_delay * (2 ** (attempt - 1))
            logger.info("%s: retrying in %.1fs...", operation_name, delay)
            await asyncio.sleep(delay)
    
    # All retries exhausted
    logger.error(
        "%s: all %d attempts failed",
        operation_name,
        max_retries,
    )
    raise last_error


async def retry_bundle_with_backoff(
    operations: list[tuple[Callable[[], Any], str]],
    bundle_name: str,
    max_retries: int = 3,
    base_delay: float = 2.0,
    timeout_per_attempt: float = 60.0,
) -> list[Any]:
    """
    Retry a bundle of operations together with exponential backoff.
    
    If ANY operation in the bundle fails, the entire bundle is retried.
    This ensures consistency when multiple LLM calls depend on each other.
    
    Args:
        operations: List of (async_func, name) tuples
        bundle_name: Name for logging
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        timeout_per_attempt: Timeout for the entire bundle per attempt
    
    Returns:
        List of results from all operations
    
    Raises:
        Last exception encountered if all retries fail
    """
    last_error: Optional[Exception] = None
    
    for attempt in range(1, max_retries + 1):
        start_time = time.time()
        try:
            logger.info(
                "%s: bundle attempt %d/%d (%d operations)",
                bundle_name,
                attempt,
                max_retries,
                len(operations),
            )
            
            # Execute all operations with a single timeout
            async def run_bundle():
                results = []
                for operation, op_name in operations:
                    logger.debug("%s: executing %s", bundle_name, op_name)
                    result = await operation()
                    results.append(result)
                return results
            
            results = await asyncio.wait_for(
                run_bundle(),
                timeout=timeout_per_attempt,
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "%s: bundle success in %dms (attempt %d)",
                bundle_name,
                elapsed_ms,
                attempt,
            )
            
            return results
            
        except asyncio.TimeoutError:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                "%s: bundle timeout after %dms (attempt %d/%d)",
                bundle_name,
                elapsed_ms,
                attempt,
                max_retries,
            )
            last_error = asyncio.TimeoutError(
                f"{bundle_name} timed out after {elapsed_ms}ms"
            )
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "%s: bundle failed after %dms (attempt %d/%d): %s",
                bundle_name,
                elapsed_ms,
                attempt,
                max_retries,
                str(e),
            )
            last_error = e
        
        # Exponential backoff before next retry
        if attempt < max_retries:
            delay = base_delay * (2 ** (attempt - 1))
            logger.info("%s: retrying bundle in %.1fs...", bundle_name, delay)
            await asyncio.sleep(delay)
    
    # All retries exhausted
    logger.error(
        "%s: bundle failed after %d attempts",
        bundle_name,
        max_retries,
    )
    raise last_error
