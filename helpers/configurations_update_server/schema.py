import subprocess

import graphene

import scheduler


class Query(graphene.ObjectType):
    class Meta:
        description = 'The API for the configuration update server.'

    reload_qtile = graphene.Boolean(name="reload_qtile", description='Reload the qtile configuration.')

    def resolve_reload_qtile(root, info):
        scheduler.schedule()
        subprocess.run(["qtile", "cmd-obj", "-o", "cmd", "-f", "reload_config"])
        return True


schema = graphene.Schema(query=Query)


if __name__ == '__main__':
    pass