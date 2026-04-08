"""
Test suite for RabbitMQ health check endpoint.

This test verifies the health check endpoint that monitors RabbitMQ broker
connectivity and returns status information.

**Validates: Requirements 7.3, 7.4**
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from app.api.v1.health import check_rabbitmq_health


class TestRabbitMQHealthCheck:
    """Test RabbitMQ health check endpoint functionality."""
    
    @pytest.mark.asyncio
    async def test_health_check_returns_healthy_status_with_workers(self):
        """
        Verify health check returns healthy status when workers are connected.
        
        **Validates: Requirement 7.3**
        """
        # Mock the Celery inspect API
        mock_inspect = MagicMock()
        mock_inspect.active_queues.return_value = {
            'worker1@hostname': [
                {'name': 'celery', 'exchange': {'name': 'celery'}, 'routing_key': 'celery'}
            ],
            'worker2@hostname': [
                {'name': 'celery', 'exchange': {'name': 'celery'}, 'routing_key': 'celery'}
            ]
        }
        mock_inspect.stats.return_value = {
            'worker1@hostname': {'pool': {'max-concurrency': 4}},
            'worker2@hostname': {'pool': {'max-concurrency': 4}}
        }
        
        with patch('app.api.v1.health.celery_app.control.inspect', return_value=mock_inspect):
            result = await check_rabbitmq_health()
        
        # Verify response structure
        assert result['status'] == 'healthy'
        assert result['broker'] == 'rabbitmq'
        assert result['active_workers'] == 2
        assert len(result['workers']) == 2
        assert 'worker1@hostname' in result['workers']
        assert 'worker2@hostname' in result['workers']
        assert 'celery' in result['queues']
        assert result['worker_stats'] is not None
    
    @pytest.mark.asyncio
    async def test_health_check_returns_503_when_no_workers(self):
        """
        Verify health check returns 503 status when no workers are connected.
        
        **Validates: Requirement 7.4**
        """
        # Mock the Celery inspect API to return None (no workers)
        mock_inspect = MagicMock()
        mock_inspect.active_queues.return_value = None
        
        with patch('app.api.v1.health.celery_app.control.inspect', return_value=mock_inspect):
            with pytest.raises(HTTPException) as exc_info:
                await check_rabbitmq_health()
        
        # Verify 503 status code
        assert exc_info.value.status_code == 503
        assert "Cannot connect to RabbitMQ broker" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_health_check_handles_connection_exception(self):
        """
        Verify health check handles connection exceptions gracefully.
        
        **Validates: Requirement 7.4**
        """
        # Mock the Celery inspect API to raise an exception
        mock_inspect = MagicMock()
        mock_inspect.active_queues.side_effect = ConnectionError("Connection refused")
        
        with patch('app.api.v1.health.celery_app.control.inspect', return_value=mock_inspect):
            with pytest.raises(HTTPException) as exc_info:
                await check_rabbitmq_health()
        
        # Verify 503 status code and error message
        assert exc_info.value.status_code == 503
        assert "RabbitMQ health check failed" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_health_check_returns_empty_workers_list_when_no_active_workers(self):
        """
        Verify health check returns empty workers list when workers dict is empty.
        
        **Validates: Requirement 7.3**
        """
        # Mock the Celery inspect API with empty workers dict
        mock_inspect = MagicMock()
        mock_inspect.active_queues.return_value = {}
        mock_inspect.stats.return_value = {}
        
        with patch('app.api.v1.health.celery_app.control.inspect', return_value=mock_inspect):
            result = await check_rabbitmq_health()
        
        # Verify response indicates no workers but still healthy (broker is up)
        assert result['status'] == 'healthy'
        assert result['broker'] == 'rabbitmq'
        assert result['active_workers'] == 0
        assert result['workers'] == []
        assert result['queues'] == []
    
    @pytest.mark.asyncio
    async def test_health_check_extracts_multiple_queue_names(self):
        """
        Verify health check correctly extracts queue names from multiple workers.
        
        **Validates: Requirement 7.3**
        """
        # Mock the Celery inspect API with multiple queues
        mock_inspect = MagicMock()
        mock_inspect.active_queues.return_value = {
            'worker1@hostname': [
                {'name': 'celery', 'exchange': {'name': 'celery'}},
                {'name': 'priority', 'exchange': {'name': 'priority'}}
            ],
            'worker2@hostname': [
                {'name': 'celery', 'exchange': {'name': 'celery'}}
            ]
        }
        mock_inspect.stats.return_value = {
            'worker1@hostname': {},
            'worker2@hostname': {}
        }
        
        with patch('app.api.v1.health.celery_app.control.inspect', return_value=mock_inspect):
            result = await check_rabbitmq_health()
        
        # Verify unique queue names are extracted
        assert result['active_workers'] == 2
        assert len(result['queues']) == 2
        assert 'celery' in result['queues']
        assert 'priority' in result['queues']
