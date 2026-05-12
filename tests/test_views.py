"""Unit tests for views and API endpoints."""

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
import json
from unittest.mock import patch, Mock
from dashboard.models import Service, GrafanaPanel


@pytest.mark.django_db
@pytest.mark.unit
@pytest.mark.views
class TestDashboardView:
    """Test cases for the main dashboard view."""
    
    @pytest.mark.skip(reason="Python 3.14 has a Django template context copy bug - skip this HTML rendering test")
    def test_dashboard_loads(self, api_client):
        """Test that dashboard page loads successfully."""
        response = api_client.get('/')
        
        assert response.status_code == 200
        assert b'HomeLab' in response.content or b'Dashboard' in response.content
    
    @pytest.mark.skip(reason="Python 3.14 has a Django template context copy bug - skip this HTML rendering test")
    def test_dashboard_with_services(self, api_client, sample_services):
        """Test dashboard displays services."""
        response = api_client.get('/')
        
        assert response.status_code == 200
        # Check context data
        assert 'services' in response.context
        assert response.context['total_services'] == 5
        assert response.context['up_services'] == 3  # Based on sample_services fixture
        assert response.context['down_services'] == 2
    
    @pytest.mark.skip(reason="Python 3.14 has a Django template context copy bug - skip this HTML rendering test")
    def test_dashboard_with_grafana_panels(self, api_client, grafana_panel):
        """Test dashboard includes Grafana panels."""
        response = api_client.get('/')
        
        assert response.status_code == 200
        assert 'grafana_panels' in response.context
        assert len(response.context['grafana_panels']) > 0
    
    @pytest.mark.skip(reason="Python 3.14 has a Django template context copy bug - skip this HTML rendering test")
    def test_dashboard_empty_state(self, api_client, db):
        """Test dashboard with no services."""
        response = api_client.get('/')
        
        assert response.status_code == 200
        assert response.context['total_services'] == 0


@pytest.mark.django_db
@pytest.mark.unit
@pytest.mark.views
class TestServiceAPIEndpoints:
    """Test cases for service API endpoints."""
    
    def test_api_services_list(self, api_client, sample_services, db):
        """Test getting list of services via API."""
        from dashboard.models import Service
        # Clean up any existing services first
        Service.objects.all().delete()
        # Recreate the sample services
        for i, service in enumerate(sample_services):
            service.save()
        
        response = api_client.get('/api/services/')
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert 'services' in data
        assert 'total' in data
        assert data['total'] == 5
        assert len(data['services']) == 5
    
    def test_api_services_structure(self, api_client, sample_service):
        """Test structure of service API response."""
        response = api_client.get('/api/services/')
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        service = data['services'][0]
        assert 'id' in service
        assert 'name' in service
        assert 'url' in service
        assert 'status' in service
        assert 'service_type' in service
        assert 'provider' in service
    
    def test_api_services_empty(self, api_client, db):
        """Test API with no services."""
        from dashboard.models import Service
        # Ensure database is clean
        Service.objects.all().delete()
        
        response = api_client.get('/api/services/')
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert data['total'] == 0
        assert data['services'] == []
    
    @patch('dashboard.views.sync_traefik_services')
    @patch('dashboard.utils.traefik_service.is_traefik_configured')
    @patch('dashboard.utils.traefik_service.check_traefik_availability')
    def test_refresh_services_with_traefik(self, mock_availability, mock_configured, 
                                          mock_sync, api_client, sample_service):
        """Test refreshing services with Traefik available."""
        mock_configured.return_value = True
        mock_availability.return_value = True
        mock_sync.return_value = 2
        
        response = api_client.post('/api/services/refresh/')
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert data['success'] is True
        assert 'synced_services' in data
        assert 'health_checks' in data
        assert data['traefik_configured'] is True
        assert data['traefik_available'] is True
    
    @patch('dashboard.utils.traefik_service.is_traefik_configured')
    @patch('dashboard.utils.traefik_service.check_traefik_availability')
    def test_refresh_services_without_traefik(self, mock_availability, mock_configured,
                                             api_client, sample_service):
        """Test refreshing services without Traefik."""
        mock_configured.return_value = False
        mock_availability.return_value = False
        
        response = api_client.post('/api/services/refresh/')
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert data['success'] is True
        assert data['traefik_configured'] is False
        assert 'info' in data
    
    def test_check_service_health(self, api_client, sample_service, mock_requests_success):
        """Test checking individual service health."""
        url = f'/api/services/{sample_service.id}/check-health/'
        response = api_client.post(url)
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert data['success'] is True
        assert data['service_id'] == sample_service.id
        assert 'status' in data
    
    def test_check_nonexistent_service_health(self, api_client, db):
        """Test checking health of non-existent service."""
        response = api_client.post('/api/services/99999/check-health/')
        
        assert response.status_code == 404
        data = json.loads(response.content)
        assert data['success'] is False

    @patch('dashboard.views.run_service_health_check')
    def test_check_services_health_bulk(self, mock_health_check, api_client, sample_services):
        """Test checking all services health without Traefik sync."""
        mock_health_check.return_value = None

        response = api_client.post('/api/services/health/')

        assert response.status_code == 200
        data = json.loads(response.content)

        assert data['success'] is True
        assert data['health_checks'] == len(sample_services)
        assert data['total'] == len(sample_services)
        assert len(data['services']) == len(sample_services)
        assert mock_health_check.call_count == len(sample_services)

    def test_update_qbittorrent_credentials(self, api_client, sample_service):
        """Test saving qBittorrent username/password credentials."""
        response = api_client.post(
            f'/api/services/{sample_service.id}/credentials/',
            data=json.dumps({
                'api_type': 'qBittorrent',
                'api_url': 'qbittorrent.local',
                'auth_method': 'basic',
                'api_username': ' admin ',
                'api_password': '1qaz"WSX',
                'api_key': 'old-api-key',
            }),
            content_type='application/json',
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['success'] is True

        sample_service.refresh_from_db()
        assert sample_service.api_type == 'qbittorrent'
        assert sample_service.api_url == 'https://qbittorrent.local'
        assert sample_service.api_username == 'admin'
        assert sample_service.api_password == '1qaz"WSX'
        assert sample_service.api_key == ''
        assert sample_service.api_detected is True
        assert sample_service.api_endpoint == '/api/v2'

    def test_update_qbittorrent_api_key_credentials(self, api_client, sample_service):
        """Test saving qBittorrent API key credentials clears username/password."""
        response = api_client.post(
            f'/api/services/{sample_service.id}/credentials/',
            data=json.dumps({
                'api_type': 'qBittorrent',
                'api_url': 'qbittorrent.local',
                'auth_method': 'api_key',
                'api_username': 'admin',
                'api_password': 'old-password',
                'api_key': 'qb-api-key-123',
            }),
            content_type='application/json',
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['success'] is True

        sample_service.refresh_from_db()
        assert sample_service.api_type == 'qbittorrent'
        assert sample_service.api_username == ''
        assert sample_service.api_password == ''
        assert sample_service.api_key == 'qb-api-key-123'
        assert sample_service.api_detected is True
        assert sample_service.api_endpoint == '/api/v2'

    def test_qbittorrent_api_docs_include_wiki_reference(self, api_client, sample_service):
        """Test qBittorrent API docs include official wiki references."""
        sample_service.api_type = 'qbittorrent'
        sample_service.api_url = 'https://qbittorrent.local'
        sample_service.api_detected = True
        sample_service.save()

        response = api_client.get(f'/api/services/{sample_service.id}/api-docs/')

        assert response.status_code == 200
        data = json.loads(response.content)
        references = data['documentation']['references']
        urls = [reference['url'] for reference in references]

        assert 'https://github.com/qbittorrent/qBittorrent/wiki/' in urls
        assert 'https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API' in urls


@pytest.mark.django_db
@pytest.mark.unit
@pytest.mark.views
class TestServiceDetailView:
    """Test cases for service detail view."""
    
    def test_service_detail_loads(self, api_client, sample_service):
        """Test service detail page loads."""
        url = f'/service/{sample_service.id}/'
        response = api_client.get(url)
        
        assert response.status_code == 200
        assert sample_service.name.encode() in response.content
    
    def test_service_detail_with_api(self, api_client, service_with_api):
        """Test service detail page with API integration."""
        url = f'/service/{service_with_api.id}/'
        response = api_client.get(url)
        
        assert response.status_code == 200
        assert 'API' in str(response.content) or 'api' in str(response.content)
    
    def test_service_detail_not_found(self, api_client, db):
        """Test service detail with invalid ID."""
        response = api_client.get('/service/99999/')
        
        assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.unit
@pytest.mark.views
class TestServiceManagementViews:
    """Test cases for service management (create, update, delete)."""
    
    def test_create_service_requires_post(self, api_client):
        """Test create service API rejects GET requests."""
        response = api_client.get('/api/services/create/')

        assert response.status_code == 405

    @patch('dashboard.models.Service.check_health')
    def test_create_service_post(self, mock_check_health, api_client, db):
        """Test POST request to create new service."""
        mock_check_health.return_value = 'up'
        data = {
            'name': 'New Test Service',
            'url': 'https://newtest.local',
            'service_type': 'docker',
            'description': 'A new test service',
            'provider': 'local',
        }
        
        response = api_client.post(
            '/api/services/create/',
            data=json.dumps(data),
            content_type='application/json',
        )
        
        assert response.status_code == 200
        assert Service.objects.filter(name='New Test Service', is_manual=True).exists()

    @patch('dashboard.models.Service.check_health')
    def test_update_service_view(self, mock_check_health, api_client, sample_service):
        """Test updating a manual service."""
        mock_check_health.return_value = 'up'
        sample_service.is_manual = True
        sample_service.save()

        response = api_client.post(
            f'/api/services/{sample_service.id}/update/',
            data=json.dumps({'name': 'Updated Test Service'}),
            content_type='application/json',
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['success'] is True

        sample_service.refresh_from_db()
        assert sample_service.name == 'Updated Test Service'
    
    def test_delete_service_view(self, api_client, sample_service):
        """Test deleting a service."""
        sample_service.is_manual = True
        sample_service.save()
        service_id = sample_service.id
        url = f'/api/services/{service_id}/delete/'
        
        response = api_client.post(url)
        
        assert response.status_code == 200
        assert not Service.objects.filter(id=service_id).exists()


@pytest.mark.django_db
@pytest.mark.unit
@pytest.mark.views
class TestGrafanaPanelViews:
    """Test cases for Grafana panel views."""
    
    def test_grafana_panels_list(self, api_client, grafana_panel):
        """Test listing Grafana panels."""
        response = api_client.get('/grafana/')
        
        assert response.status_code == 200
        assert grafana_panel.title.encode() in response.content
    
    def test_grafana_panel_detail(self, api_client, grafana_panel):
        """Test Grafana panel detail view."""
        url = f'/grafana/{grafana_panel.id}/'
        response = api_client.get(url)
        
        assert response.status_code == 200
        assert grafana_panel.title.encode() in response.content


@pytest.mark.django_db
@pytest.mark.unit
@pytest.mark.views
class TestQBittorrentView:
    """Test cases for qBittorrent dashboard view."""
    
    @patch('dashboard.views.GenericAPIClient')
    def test_qbittorrent_dashboard_with_service(self, mock_client, api_client, service_with_api):
        """Test qBittorrent dashboard with configured service."""
        # Update service to be qbittorrent type
        service_with_api.api_type = 'qbittorrent'
        service_with_api.save()
        
        # Mock API response
        mock_instance = Mock()
        mock_instance.get_torrent_list.return_value = []
        mock_client.return_value = mock_instance
        
        url = f'/qbittorrent/{service_with_api.id}/'
        response = api_client.get(url)
        
        # Should load successfully or redirect
        assert response.status_code in [200, 302, 404]
    
    def test_qbittorrent_dashboard_no_service(self, api_client, db):
        """Test qBittorrent dashboard with no service configured."""
        response = api_client.get('/qbittorrent/99999/')
        
        assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.unit
@pytest.mark.views  
class TestAPIDetectionViews:
    """Test cases for API detection endpoints."""
    
    @patch('dashboard.utils.api_detector.APIDetector.detect_api')
    def test_detect_api_endpoint(self, mock_detect, api_client, sample_service):
        """Test API detection endpoint."""
        mock_detect.return_value = (True, 'qbittorrent', '/api/v2')
        
        url = f'/api/services/{sample_service.id}/detect-api/'
        response = api_client.post(url)
        
        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert 'success' in data or 'detected' in data
