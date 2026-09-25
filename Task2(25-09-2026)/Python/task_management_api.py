"""
Task Management API using FastAPI.

"""

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(
    title="Task Management API",
    description="CRUD API for managing tasks",
    version="1.0.0"
)


# Request model
class TaskCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        description="Task title"
    )

    description: Optional[str] = None

    completed: bool = False


# Response model
class Task(TaskCreate):
    id: int


# Temporary in-memory storage
tasks = []

next_id = 1


# ============================================
# CREATE TASK
# ============================================

@app.post(
    "/tasks",
    response_model=Task,
    status_code=201
)
def create_task(task: TaskCreate):

    global next_id

    title = task.title.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Task title cannot be empty"
        )

    new_task = Task(
        id=next_id,
        title=title,
        description=task.description,
        completed=task.completed
    )

    tasks.append(new_task)

    next_id += 1

    return new_task


# ============================================
# GET ALL TASKS
# ============================================

@app.get(
    "/tasks",
    response_model=list[Task]
)
def get_all_tasks():

    return tasks


# ============================================
# GET TASK BY ID
# ============================================

@app.get(
    "/tasks/{task_id}",
    response_model=Task
)
def get_task(task_id: int):

    if task_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="Task ID must be greater than zero"
        )

    for task in tasks:

        if task.id == task_id:
            return task

    raise HTTPException(
        status_code=404,
        detail="Task not found"
    )


# ============================================
# UPDATE TASK
# ============================================

@app.put(
    "/tasks/{task_id}",
    response_model=Task
)
def update_task(
    task_id: int,
    updated_task: TaskCreate
):

    if task_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="Task ID must be greater than zero"
        )

    title = updated_task.title.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Task title cannot be empty"
        )

    for index, task in enumerate(tasks):

        if task.id == task_id:

            new_task = Task(
                id=task_id,
                title=title,
                description=updated_task.description,
                completed=updated_task.completed
            )

            tasks[index] = new_task

            return new_task

    raise HTTPException(
        status_code=404,
        detail="Task not found"
    )


# ============================================
# DELETE TASK
# ============================================

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):

    if task_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="Task ID must be greater than zero"
        )

    for index, task in enumerate(tasks):

        if task.id == task_id:

            tasks.pop(index)

            return {
                "message": "Task deleted successfully"
            }

    raise HTTPException(
        status_code=404,
        detail="Task not found"
    )