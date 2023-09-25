from flask import Flask, request, jsonify, render_template, redirect, url_for
from ariadne import QueryType, MutationType, make_executable_schema, graphql_sync, load_schema_from_path
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from ariadne.explorer import ExplorerGraphiQL
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from ariadne import SchemaDirectiveVisitor
from graphql import default_field_resolver
from flask_admin import Admin

app = Flask(__name__)

explorer_html = ExplorerGraphiQL().html(None)
# Configure the database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todos.db'
db = SQLAlchemy(app)
admin = Admin(app, name='My admin', template_mode='bootstrap3')

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Add this relationship

    user = db.relationship('User', backref='todos')  # Add this relationship

    def __init__(self, title, completed=False):
        self.title = title
        self.completed = completed


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

    def __init__(self, username, password):
        self.username = username
        self.password = password


# Configure Flask-Login
app.secret_key = 'your_secret_key'  # Replace with a strong secret key
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)
@login_manager.user_loader
def load_user(user_id):
    # since the user_id is just the primary key of our user table, use it in the query for the user
    return User.query.get(int(user_id))


# Load the schema from the schema.graphql file
type_defs = load_schema_from_path("schema.graphql")

# Define your GraphQL resolvers
query = QueryType()
mutation = MutationType()

@query.field("todos")
def resolve_todos(_, info):
    return current_user.todos


@mutation.field("createTodo")
def resolve_create_todo(_, info, title):
    todo = Todo(title=title, completed=False)
    todo.user = current_user
    db.session.add(todo)
    db.session.commit()
    return todo


@mutation.field("updateTodo")
def resolve_update_todo(_, info, id, title, completed):
    todo = Todo.query.filter_by(id=id, user_id=current_user.id).first()
    if todo:
        if title is not None:
            todo.title = title
        if completed is not None:
            todo.completed = completed
        db.session.commit()
        return todo
    return None


@mutation.field("deleteTodo")
def resolve_delete_todo(_, info, id):
    todo = Todo.query.filter_by(id=id, user_id=current_user.id).first()
    if todo:
        db.session.delete(todo)
        db.session.commit()
        return todo
    return None


# Custom directive implementation
class UppercaseDirective(SchemaDirectiveVisitor):
    def visit_field_definition(self, field, object_type):
        original_resolve = field.resolve or default_field_resolver

        def uppercased_resolver(root, info, **kwargs):
            result = original_resolve(root, info, **kwargs)
            if isinstance(result, str):
                return result.upper()
            return result

        field.resolve = uppercased_resolver
        return field


class AuthDirective(SchemaDirectiveVisitor):
    def visit_field_definition(self, field, object_type):
        original_resolve = field.resolve or default_field_resolver

        def auth_resolver(root, info, **kwargs):
            if not current_user.is_authenticated:  # Check if the user is authenticated
                raise Exception("Unauthorized")  # You can customize this error message
            return original_resolve(root, info, **kwargs)

        field.resolve = auth_resolver
        return field


# Create a schema using the type definitions and add the directive
schema = make_executable_schema(type_defs, [query, mutation], directives={"uppercase": UppercaseDirective, "auth": AuthDirective})


# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        print(user)
        if user and user.password == password:
            login_user(user)
            return redirect(url_for("graphql_explorer"))
    return render_template("login.html")


# Logout route
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# Serve the GraphQL Playground at the "/graphql" route for GET requests
@app.route("/graphql", methods=["GET"])
def graphql_explorer():
    return explorer_html, 200


# GraphQL endpoint
@app.route("/graphql", methods=["POST"])
def graphql_server():
    data = request.get_json()
    success, result = graphql_sync(schema, data, context_value={"request": request})
    status_code = 200 if success else 400
    return jsonify(result), status_code

if __name__ == "__main__":
    # Create the database tables if they don't exist
    with app.app_context():
        db.create_all()
    app.run(debug=True)
