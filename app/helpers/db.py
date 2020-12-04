from flask_sqlalchemy import SQLAlchemy


from sqlalchemy import event

# from sqlalchemy.engine import Engine
# from datetime import datetime
# import time
#
#
# @event.listens_for(Engine, "before_cursor_execute")
# def before_cursor_execute(conn, cursor, statement,
#                         parameters, context, executemany):
#     conn.info.setdefault('query_start_time', []).append(time.time())
#
#
# @event.listens_for(Engine, "after_cursor_execute")
# def after_cursor_execute(conn, cursor, statement,
#                         parameters, context, executemany):
#     total = time.time() - conn.info['query_start_time'].pop(-1)
#     if total > 0.2:
#         print(f"   ----     Total Time: {round(total * 1000, 3)} ms for statement {statement}")
#         print(datetime.now())


# We want to avoid garbage collection on the sqlalchemy session, which would force new DB queries
# so we keep a strong ref of each persistent object stored in the session
def strong_reference_session(session):
    @event.listens_for(session, "pending_to_persistent")
    @event.listens_for(session, "deleted_to_persistent")
    @event.listens_for(session, "detached_to_persistent")
    @event.listens_for(session, "loaded_as_persistent")
    def strong_ref_object(sess, instance):
        if "refs" not in sess.info:
            sess.info["refs"] = refs = set()
        else:
            refs = sess.info["refs"]

        refs.add(instance)

    @event.listens_for(session, "persistent_to_detached")
    @event.listens_for(session, "persistent_to_deleted")
    @event.listens_for(session, "persistent_to_transient")
    def deref_object(sess, instance):
        sess.info["refs"].discard(instance)


class SQLAlchemyWithStrongRefSession(SQLAlchemy):
    def create_session(self, options):
        sess = super().create_session(options)
        strong_reference_session(sess)
        return sess
