"""
Unit tests for configuration assembly in app/core/config.py

Tests verify RabbitMQ URL construction, precedence rules, and default values.
Validates Requirements 5.3, 5.4, 5.5 from RabbitMQ Broker Migration spec.
"""
import pytest
import os
import sys
from unittest.mock import patch
from pathlib import Path


# Prevent .env file loading during tests by mocking it before importing config
@pytest.fixture(autouse=True)
def mock_env_file():
    """Mock the .env file to prevent it from being loaded during tests"""
    with patch.object(Path, 'exists', return_value=False):
        yield


def create_settings_with_env(**env_overrides):
    """
    Helper function to create Settings instance with specific environment variables.
    Uses pydantic's _env_file parameter to prevent .env loading.
    """
    # Start with minimal base environment
    base_env = {
        'DEBUG': 'False',
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
    }
    
    # Add overrides
    base_env.update(env_overrides)
    
    # Remove None values (can't set env vars to None)
    env_to_use = {k: v for k, v in base_env.items() if v is not None}
    
    with patch.dict(os.environ, env_to_use, clear=True):
        # Clear the module cache to force reimport
        if 'app.core.config' in sys.modules:
            del sys.modules['app.core.config']
        
        # Import Settings fresh
        from app.core.config import Settings
        
        # Create settings without loading .env file
        return Settings(_env_file=None)


class TestRabbitMQConfigurationAssembly:
    """Test RabbitMQ URL construction and configuration assembly"""
    
    def test_rabbitmq_url_construction_from_individual_parameters(self):
        """
        Test that RabbitMQ URL is correctly constructed from individual parameters
        when RABBITMQ_URL is not provided.
        
        Validates Requirement 5.4: When RABBITMQ_URL is not provided, 
        the system SHALL construct the broker URL from individual parameters.
        """
        settings = create_settings_with_env(
            RABBITMQ_HOST='rabbitmq.example.com',
            RABBITMQ_PORT='5672',
            RABBITMQ_USER='testuser',
            RABBITMQ_PASSWORD='testpass',
            RABBITMQ_VHOST='/testenv',
        )
        
        expected_url = 'amqp://testuser:testpass@rabbitmq.example.com:5672//testenv'
        assert settings.CELERY_BROKER_URL == expected_url
        assert settings.RABBITMQ_HOST == 'rabbitmq.example.com'
        assert settings.RABBITMQ_PORT == 5672
        assert settings.RABBITMQ_USER == 'testuser'
        assert settings.RABBITMQ_PASSWORD == 'testpass'
        assert settings.RABBITMQ_VHOST == '/testenv'
    
    def test_rabbitmq_url_takes_precedence_over_individual_parameters(self):
        """
        Test that RABBITMQ_URL takes precedence when both full URL 
        and individual parameters are provided.
        
        Validates Requirement 5.3: When RABBITMQ_URL is provided, 
        the system SHALL use it as the broker URL.
        """
        settings = create_settings_with_env(
            RABBITMQ_URL='amqp://priority:password@priority.host:5672/priority',
            RABBITMQ_HOST='ignored.host',
            RABBITMQ_PORT='9999',
            RABBITMQ_USER='ignored_user',
            RABBITMQ_PASSWORD='ignored_pass',
            RABBITMQ_VHOST='/ignored',
        )
        
        # RABBITMQ_URL should be used directly
        assert settings.CELERY_BROKER_URL == 'amqp://priority:password@priority.host:5672/priority'
        # Individual parameters are still stored but not used for broker URL
        assert settings.RABBITMQ_HOST == 'ignored.host'
        assert settings.RABBITMQ_USER == 'ignored_user'
    
    def test_default_values_when_no_configuration_provided(self):
        """
        Test that default values are used when no RabbitMQ configuration is provided.
        
        Validates Requirement 5.5: The system SHALL default to localhost:5672 
        with guest/guest credentials when no RabbitMQ configuration is provided.
        """
        settings = create_settings_with_env()
        
        # Verify defaults
        assert settings.RABBITMQ_HOST == 'localhost'
        assert settings.RABBITMQ_PORT == 5672
        assert settings.RABBITMQ_USER == 'guest'
        assert settings.RABBITMQ_PASSWORD == 'guest'
        assert settings.RABBITMQ_VHOST == '/'
        
        # Verify constructed URL uses defaults
        expected_default_url = 'amqp://guest:guest@localhost:5672//'
        assert settings.CELERY_BROKER_URL == expected_default_url
    
    def test_redis_result_backend_remains_configured(self):
        """
        Test that Redis result backend is correctly configured alongside RabbitMQ broker.
        
        Validates that the system maintains separate connections for RabbitMQ broker
        and Redis result backend (Requirement 4.5).
        """
        settings = create_settings_with_env(
            RABBITMQ_URL='amqp://user:pass@rabbitmq.host:5672/vhost',
            REDIS_HOST='redis.example.com',
            REDIS_PORT='6379',
            REDIS_DB='1',
            REDIS_PASSWORD='redispass',
        )
        
        # Verify RabbitMQ is used for broker
        assert settings.CELERY_BROKER_URL == 'amqp://user:pass@rabbitmq.host:5672/vhost'
        
        # Verify Redis is used for result backend
        assert 'redis://' in settings.CELERY_RESULT_BACKEND
        assert 'redis.example.com' in settings.CELERY_RESULT_BACKEND
        assert ':6379' in settings.CELERY_RESULT_BACKEND
        assert '/1' in settings.CELERY_RESULT_BACKEND
    
    def test_redis_url_construction_with_password(self):
        """
        Test that Redis URL is correctly constructed with password when provided.
        """
        settings = create_settings_with_env(
            REDIS_HOST='redis.host',
            REDIS_PORT='6379',
            REDIS_DB='0',
            REDIS_PASSWORD='secret',
        )
        
        expected_redis_url = 'redis://:secret@redis.host:6379/0'
        assert settings.CELERY_RESULT_BACKEND == expected_redis_url
    
    def test_redis_url_construction_without_password(self):
        """
        Test that Redis URL is correctly constructed without password when not provided.
        """
        settings = create_settings_with_env(
            REDIS_HOST='redis.host',
            REDIS_PORT='6379',
            REDIS_DB='0',
        )
        
        expected_redis_url = 'redis://redis.host:6379/0'
        assert settings.CELERY_RESULT_BACKEND == expected_redis_url
    
    def test_redis_url_takes_precedence(self):
        """
        Test that REDIS_URL takes precedence over individual Redis parameters.
        """
        settings = create_settings_with_env(
            REDIS_URL='redis://priority.redis:6379/5',
            REDIS_HOST='ignored.host',
            REDIS_PORT='9999',
            REDIS_DB='0',
        )
        
        assert settings.CELERY_RESULT_BACKEND == 'redis://priority.redis:6379/5'
    
    def test_rabbitmq_vhost_with_slash_prefix(self):
        """
        Test that vhost with leading slash is correctly handled in URL construction.
        """
        settings = create_settings_with_env(
            RABBITMQ_HOST='localhost',
            RABBITMQ_PORT='5672',
            RABBITMQ_USER='user',
            RABBITMQ_PASSWORD='pass',
            RABBITMQ_VHOST='/myvhost',
        )
        
        # Vhost should be included in URL
        expected_url = 'amqp://user:pass@localhost:5672//myvhost'
        assert settings.CELERY_BROKER_URL == expected_url
    
    def test_rabbitmq_vhost_without_slash_prefix(self):
        """
        Test that vhost without leading slash is correctly handled in URL construction.
        """
        settings = create_settings_with_env(
            RABBITMQ_HOST='localhost',
            RABBITMQ_PORT='5672',
            RABBITMQ_USER='user',
            RABBITMQ_PASSWORD='pass',
            RABBITMQ_VHOST='myvhost',
        )
        
        # Vhost should be included in URL
        expected_url = 'amqp://user:pass@localhost:5672/myvhost'
        assert settings.CELERY_BROKER_URL == expected_url
    
    def test_special_characters_in_credentials(self):
        """
        Test that special characters in username and password are handled correctly.
        Note: In production, these should be URL-encoded, but this tests current behavior.
        """
        settings = create_settings_with_env(
            RABBITMQ_HOST='localhost',
            RABBITMQ_PORT='5672',
            RABBITMQ_USER='user@domain',
            RABBITMQ_PASSWORD='p@ss:word!',
            RABBITMQ_VHOST='/',
        )
        
        # URL should contain the credentials (note: may need URL encoding in production)
        assert 'user@domain' in settings.CELERY_BROKER_URL
        assert 'p@ss:word!' in settings.CELERY_BROKER_URL
    
    def test_custom_port_configuration(self):
        """
        Test that custom RabbitMQ port is correctly used in URL construction.
        """
        settings = create_settings_with_env(
            RABBITMQ_HOST='localhost',
            RABBITMQ_PORT='15672',
            RABBITMQ_USER='guest',
            RABBITMQ_PASSWORD='guest',
            RABBITMQ_VHOST='/',
        )
        
        expected_url = 'amqp://guest:guest@localhost:15672//'
        assert settings.CELERY_BROKER_URL == expected_url
        assert settings.RABBITMQ_PORT == 15672


class TestConfigurationIntegrity:
    """Test that configuration maintains integrity across different scenarios"""
    
    def test_both_broker_and_backend_configured_simultaneously(self):
        """
        Test that both RabbitMQ broker and Redis backend can be configured
        simultaneously without conflicts.
        """
        settings = create_settings_with_env(
            RABBITMQ_URL='amqp://rmq:pass@rabbitmq:5672/prod',
            REDIS_URL='redis://redis:6379/0',
        )
        
        # Both should be configured correctly
        assert settings.CELERY_BROKER_URL == 'amqp://rmq:pass@rabbitmq:5672/prod'
        assert settings.CELERY_RESULT_BACKEND == 'redis://redis:6379/0'
        
        # Verify they are different
        assert settings.CELERY_BROKER_URL != settings.CELERY_RESULT_BACKEND
        assert 'amqp://' in settings.CELERY_BROKER_URL
        assert 'redis://' in settings.CELERY_RESULT_BACKEND
    
    def test_configuration_with_minimal_environment(self):
        """
        Test that configuration works with minimal environment variables,
        relying on defaults for most values.
        """
        settings = create_settings_with_env(
            RABBITMQ_HOST='rabbitmq',
            REDIS_HOST='redis',
        )
        
        # Should use provided hosts with default ports and credentials
        assert 'rabbitmq' in settings.CELERY_BROKER_URL
        assert '5672' in settings.CELERY_BROKER_URL
        assert 'guest' in settings.CELERY_BROKER_URL
        
        assert 'redis' in settings.CELERY_RESULT_BACKEND
        assert '6379' in settings.CELERY_RESULT_BACKEND
