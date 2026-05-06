import { fetchConversations } from "../api/messages.js";
import { usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";

function MessagesView({ user }) {
  const { data, error, loading } = useAsync(fetchConversations, []);
  if (!user) return <AuthRequired />;
  return (
    <PageShell kicker="mesaje" title="Conversații" sub="Mesajele contului tău.">
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca mesajele">{error}</StatusPanel> : null}
      {data?.conversations?.length ? (
        <div className="list-grid">
          {data.conversations.map((conversation) => (
            <div className="piece-card" key={conversation.id}>
              <div className="piece-card-kicker">{conversation.unread_count ? `${conversation.unread_count} necitite` : "conversație"}</div>
              <h2 className="piece-card-title">{usernameHandle(conversation.other_user?.username)}</h2>
              <p className="piece-card-excerpt">{conversation.latest_message?.content || "Fără mesaje încă."}</p>
            </div>
          ))}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu ai conversații încă" /> : null}
    </PageShell>
  );
}

export default function MessagesRoute({ user }) {
  return <MessagesView user={user} />;
}
