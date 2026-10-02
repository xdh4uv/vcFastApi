import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import test_learning as fixture
from test_learning import COURSE
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.aptitudeModel import AptitudeProfile, Enrollment
from app.models.tutorModel import DoubtTurn, SavedNote
from app.models.engagementModel import ReadingProgress, LearningEvent, AttemptTiming
from app.routers import learning, tutor


class Phase1ApiTests(unittest.TestCase):
    def setUp(self):
        fixture.LearningTests.setUp(self)
        for model in (ReadingProgress, LearningEvent, AttemptTiming, DoubtTurn, SavedNote, Enrollment, AptitudeProfile):
            model.__table__.create(self.engine)
        self.flag = patch.object(learning.settings, 'engagement_enabled', True)
        self.tutor_flag = patch.object(learning.settings, 'tutor_enabled', False)
        self.flag.start(); self.tutor_flag.start()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.headers = {'Authorization': 'Bearer ' + create_access_token(str(self.user.id))}

    def tearDown(self):
        app.dependency_overrides.clear()
        self.flag.stop(); self.tutor_flag.stop(); self.client.close()
        fixture.LearningTests.tearDown(self)

    def test_enrollment_enforces_course_and_chapter_access(self):
        path = '/learning/courses/' + COURSE
        self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 403)
        self.assertEqual(self.client.post('/learning/subjects/' + str(self.subject.sub_module_id) + '/enroll', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 200)
        lesson = self.client.get(path + '/chapters/ch-01', headers=self.headers)
        self.assertEqual(lesson.status_code, 200)
        self.assertIsNotNone(lesson.json()['readingProgress'])
        self.assertNotIn('questions', lesson.json())

    def test_notes_catalog_route_and_disabled_tutor_contract(self):
        self.client.post('/learning/subjects/' + str(self.subject.sub_module_id) + '/enroll', headers=self.headers)
        self.assertEqual(self.client.get('/learning/notes/catalog', headers=self.headers).json(), [])
        self.assertEqual(self.client.get('/learning/notes', headers=self.headers).json(), {'notes': [], 'hasMore': False})
        history = self.client.get('/learning/courses/' + COURSE + '/chapters/ch-01/doubts', headers=self.headers)
        self.assertEqual(history.json(), {'enabled': False, 'turns': []})
        self.assertEqual(self.client.post('/learning/courses/' + COURSE + '/chapters/ch-01/doubts', headers=self.headers,
            json={'requestId': '00000000-0000-0000-0000-000000000001', 'question': 'Explain Euclid'}).status_code, 503)
