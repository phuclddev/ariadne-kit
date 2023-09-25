from ariadne import make_executable_schema, gql, QueryType, ObjectType
from ariadne.asgi import GraphQL
from ariadne import SchemaDirectiveVisitor
from graphql import default_field_resolver
import uvicorn
from flask_login import current_user

# Define your GraphQL type definitions
type_defs = gql("""
    directive @uppercase on FIELD_DEFINITION
    directive @auth on FIELD_DEFINITION

    type Author {
        id: ID!
        name: String!
    }

    type Book {
        id: ID!
        title: String! @uppercase
        author: Author!
    }

    type Query {
        books: [Book!] @auth
    }
""")

# Create resolver functions
query = QueryType()

@query.field("books")
def resolve_books(_, info):
    # Your resolver logic to fetch books
    books = [
        {"id": "1", "title": "The Catcher in the Rye", "author": {"id": "1", "name": "J.D. Salinger"}},
        {"id": "2", "title": "To Kill a Mockingbird", "author": {"id": "2", "name": "Harper Lee"}},
    ]
    return books

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

# Custom auth directive implementation
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
schema = make_executable_schema(type_defs, [query], directives={"uppercase": UppercaseDirective, "auth": AuthDirective})

# Create an ASGI app
app = GraphQL(schema, debug=True)

# To run the app, you would typically use an ASGI server such as uvicorn.
# Example: uvicorn your_module:app
# Start the server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)