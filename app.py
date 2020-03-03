import re
import uuid
from functools import wraps

from flask import Flask, jsonify, abort, make_response, request, url_for, escape
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
app.config.from_pyfile("config.cfg")
db = SQLAlchemy(app)
migrate = Migrate(app, db)


BASE_URL = "http://127.0.0.1:8000/todo/api/v1.0/"


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50))
    description = db.Column(db.Text)
    done = db.Column(db.Boolean, default=False)
    uri = db.Column(db.String(100))
    
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(128), unique=True, nullable=False)

    tasks = db.relationship("Task", backref="tasks", lazy="dynamic")    


@app.errorhandler(400)
def bad_request(error):
    return make_response(jsonify({"result": False}), 400)


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({"result": False}), 404)


@app.errorhandler(403)
def forbbiden(error):
    return make_response(jsonify({"result": False}), 403)


@app.errorhandler(500)
def internal_server_error(error):
    return make_response(jsonify({"result": False}), 500)


def generate_task_uri(task, token):
    url = url_for("get_task", task_id=task.id, token=token, _external=True)
    split = re.split(r"(tasks/\d*)", url)
    task.uri = BASE_URL+split[1]    
    db.session.add(task)
    db.session.commit()


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            user = User.query.filter(User.token==kwargs.get("token")).one()
        except Exception:
            abort(403)
        
        return func(*args, **kwargs)
    return wrapper


@app.route("/todo/api/v1.0/users", methods=["POST"])
def create_user():
    user = User(token=uuid.uuid4().hex)
    
    try:
        db.session.add(user)
        db.session.commit()
    except Exception:
        abort(500) 

    return jsonify({"result": True, "token": user.token}), 201
    

@app.route("/todo/api/v1.0/users/<string:token>", methods=["GET"])
@login_required
def get_user(token):
    user = User.query.filter(User.token==token).one()
    tasks_list = []
    for task in user.tasks:
         task_dict = {}
         task_dict["title"] = task.title
         task_dict["description"] = task.description
         task_dict["done"] = task.done
         task_dict["uri"] = task.uri
        
         tasks_list.append(task_dict)        

    return jsonify({
        "result": True, 
        "tasks": tasks_list
    }), 200 


@app.route("/todo/api/v1.0/users/<string:token>", methods=["DELETE"])
@login_required
def delete_user(token):
    user = User.query.filter(User.token==token).one()
    
    try:
        db.session.delete(user)
        db.session.commit()
    except Exception:
        abort(500) 

    return jsonify({"result": True}), 200


@app.route("/todo/api/v1.0/tasks/<string:token>", methods=["GET"])
@login_required
def get_tasks(token):
    tasks = Task.query.join(User).filter(User.token==token).all()
    
    tasks_list = []
    for task in tasks:
        task_dict = {}
        task_dict["id"] = task.id
        task_dict["title"] = task.title
        task_dict["description"] = task.description
        task_dict["done"] = task.done
        task_dict["uri"] = task.uri
        
        tasks_list.append(task_dict)        

    return jsonify(tasks_list)


@app.route("/todo/api/v1.0/tasks/<int:task_id>/<string:token>", methods=["GET"])
@login_required
def get_task(task_id, token):
    try:
        task = Task.query.join(User).filter(
                                         Task.id==task_id,
                                         User.token==token).one()
    except Exception:
        abort(404)
  
    return jsonify({
        "title": task.title,
        "description": task.description,
        "done": task.done,
        "uri": task.uri
    })


@app.route("/todo/api/v1.0/tasks/<string:token>", methods=["POST"])
@login_required
def create_task(token):
    if not request.json	or not "title" in request.json:
        abort(400)

    new_task = Task(
        title=request.json.get("title"),
        description=request.json.get("description"),
        done=False,
        user_id=User.query.filter(User.token==token).one_or_none().id
    )
  
    try: 
        db.session.add(new_task)
        db.session.commit()
        generate_task_uri(new_task, token)
    except Exception:
        db.session.rollback()
        abort(500)

    return jsonify({
        "id": new_task.id,
        "title": new_task.title,
        "description": new_task.description,
        "done": new_task.done,
        "uri": new_task.uri
    }), 201 


@app.route("/todo/api/v1.0/tasks/<int:task_id>/<string:token>", methods=["PUT"])
@login_required
def update_task(task_id, token):
    task = Task.query.join(User).filter(
                                     User.token==token, 
                                     Task.id==task_id).one_or_none()
  
    if task is None:
        abort(404)

    if not request.json:
        abort(400)

    task.title = request.json.get("title", task.title)
    task.description = request.json.get("description", task.description)
    task.done = request.json.get("done", task.done)

    try:
        db.session.add(task)
        db.session.commit()
    except Exception:
        abort(500)
    
    return jsonify({
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "done": task.done
    })


@app.route("/todo/api/v1.0/tasks/<int:task_id>/<string:token>", methods=["DELETE"])
@login_required
def delete_task(task_id, token):
    task = Task.query.join(User).filter(
                                     User.token==token, 
                                     Task.id==task_id).one_or_none()

    if task is None:
        abort(404)

    try:
        db.session.delete(task)
        db.session.commit()
    except Exception:
        abort(500)
  
    return jsonify({"result": True}), 200

