from django.db import models

# Create your models here.


class Subject(models.Model):
    name = models.TextField()
    teacher = models.ForeignKey("Teacher", on_delete=models.CASCADE)


class Teacher(models.Model):
    name = models.TextField()


class Student(models.Model):
    name = models.TextField()
    subjects = models.ManyToManyField(Subject)
