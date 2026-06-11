"""DB integration tests for ChatService."""
import uuid

from app.services.chat_service import ChatService


class TestChatService:
    def test_create_session(self, db, admin_user):
        s = ChatService(db).create_session(admin_user, title="My Chat")
        assert s.id is not None
        assert s.title == "My Chat"
        assert s.user_id == admin_user.id
        assert s.tenant_id == admin_user.tenant_id

    def test_create_session_default_title(self, db, admin_user):
        s = ChatService(db).create_session(admin_user)
        assert s.title == "New Chat"

    def test_list_sessions_returns_own(self, db, admin_user):
        svc = ChatService(db)
        svc.create_session(admin_user, "A")
        svc.create_session(admin_user, "B")
        assert len(svc.list_sessions(admin_user)) == 2

    def test_list_sessions_excludes_other_user(self, db, admin_user, analyst_user):
        ChatService(db).create_session(admin_user, "Admin chat")
        assert len(ChatService(db).list_sessions(analyst_user)) == 0

    def test_get_session_by_id(self, db, admin_user):
        svc = ChatService(db)
        s = svc.create_session(admin_user, "Test")
        found = svc.get_session(s.id, admin_user)
        assert found is not None and found.id == s.id

    def test_get_session_wrong_user_returns_none(self, db, admin_user, analyst_user):
        s = ChatService(db).create_session(admin_user, "Private")
        assert ChatService(db).get_session(s.id, analyst_user) is None

    def test_delete_session_returns_true(self, db, admin_user):
        s = ChatService(db).create_session(admin_user)
        assert ChatService(db).delete_session(s.id, admin_user) is True

    def test_delete_nonexistent_returns_false(self, db, admin_user):
        assert ChatService(db).delete_session(uuid.uuid4(), admin_user) is False

    def test_add_message_basic(self, db, admin_user):
        svc = ChatService(db)
        s = svc.create_session(admin_user)
        msg = svc.add_message(s.id, "user", "Hello!")
        assert msg.id is not None
        assert msg.content == "Hello!"
        assert msg.role == "user"

    def test_add_message_with_metadata(self, db, admin_user):
        svc = ChatService(db)
        s = svc.create_session(admin_user)
        msg = svc.add_message(
            s.id, "assistant", "Answer",
            retrieved_doc_ids=["doc-1"],
            latency_ms=250,
        )
        assert msg.latency_ms == 250

    def test_get_context_messages_ordered_chronologically(self, db, admin_user):
        svc = ChatService(db)
        s = svc.create_session(admin_user)
        svc.add_message(s.id, "user", "First")
        svc.add_message(s.id, "assistant", "Second")
        svc.add_message(s.id, "user", "Third")
        msgs = svc.get_context_messages(s.id)
        assert [m.content for m in msgs] == ["First", "Second", "Third"]

    def test_update_session_title(self, db, admin_user):
        svc = ChatService(db)
        s = svc.create_session(admin_user, "Old")
        updated = svc.update_session_title(s, "New Title")
        assert updated.title == "New Title"

    def test_deleted_session_not_retrievable(self, db, admin_user):
        svc = ChatService(db)
        s = svc.create_session(admin_user)
        svc.delete_session(s.id, admin_user)
        assert svc.get_session(s.id, admin_user) is None
