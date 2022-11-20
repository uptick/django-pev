from django.test import TestCase

from django_pev import explain
from example.school.models import Student, Subject, Teacher


class TestExplain(TestCase):
    @classmethod
    def setUpTestData(cls):
        maths_teacher = Teacher.objects.create(name="Maths Teacher")
        english_teacher = Teacher.objects.create(name="English Teacher")
        maths = Subject.objects.create(name="Maths", teacher=maths_teacher)
        english = Subject.objects.create(name="English", teacher=english_teacher)

        for _ in range(10):
            student = Student.objects.create(name="a")
            student.subjects.set([maths, english])
            student.save()

    def test_explain_captures_queries(self):
        with explain(db_alias="default") as e:
            list(Student.objects.filter(name="lol"))
            Student.objects.create(name="1")
            list(Student.objects.raw("select school_student.*, pg_sleep(0.01) from school_student"))

        assert e.n_queries == 3, "We should have captured 3 queries"

        assert "pg_sleep" in e.slowest.sql, "The slowest query should be the one with pg_sleep"

    def test_upload_plan_to_dalibo(self):
        # We can upload results to dalibo
        with explain() as e:
            list(Student.objects.filter(name="1"))

        # We can upload the result to pev
        pev_result = e.slowest.visualize(upload_query=True, title="Some test query")

        # We can delete the results
        pev_result.delete()

    def test_open_visualization_in_browser(self):
        # We can upload results to dalibo
        with explain() as e:
            list(Student.objects.filter(name="1"))

        pev_result = e.slowest.visualize_in_browser()

        pev_result.delete()
