import flask
from graphql_server.flask import GraphQLView

import schema


app = flask.Flask(__name__)
app.add_url_rule(
    "/graphql",
    view_func=GraphQLView.as_view(
        "graphql",
        schema=schema.schema,
        graphiql=True,
    ),
)


if __name__ == "__main__":
    app.run()
