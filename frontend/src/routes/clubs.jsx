import { Fragment } from "react";
import { fetchClub, fetchClubs } from "../api/clubs.js";
import { AuthorLink } from "../app/content.jsx";
import { categoryLabel, usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AdSlot, PageShell, StatusPanel } from "../app/layout.jsx";
import { blogUrl, mainPath } from "../app/paths.js";

function ClubsView() {
  const { data, error, loading } = useAsync(fetchClubs, []);
  return (
    <PageShell kicker="cluburi" title="Cluburi literare" sub="Comunități pentru poezie și proză scurtă.">
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca cluburile">{error}</StatusPanel> : null}
      {data?.clubs?.length ? (
        <div className="list-grid">
          {data.clubs.map((club, index) => (
            <Fragment key={club.id}>
              <article className="piece-card">
                <div className="piece-card-kicker">{categoryLabel(club.speciality)}</div>
                <h2 className="piece-card-title">
                  <a className="post-title-link" href={mainPath(`/cluburi/${club.slug}`)}>{club.title}</a>
                </h2>
                <p className="piece-card-excerpt">{club.description || club.motto || "Club literar pe călimara.ro."}</p>
                <div className="piece-card-meta">
                  <span>{club.member_count} membri</span>
                  {club.owner?.username ? <AuthorLink user={club.owner} /> : null}
                </div>
              </article>
              {index === 1 ? <AdSlot placement="inline" /> : null}
            </Fragment>
          ))}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu există cluburi încă" /> : null}
    </PageShell>
  );
}
function ClubDetailView({ slug }) {
  const { data, error, loading } = useAsync(() => fetchClub(slug), [slug]);
  return (
    <PageShell kicker="club" title={data?.title ?? "Club"} sub={data?.motto || data?.description}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca clubul">{error}</StatusPanel> : null}
      {data ? (
        <div className="detail-stack">
          <div className="rail">
            <div className="rail-stat">
              <span className="rail-label">Membri</span>
              <span className="rail-count">{data.member_count}</span>
              <span className="rail-sub">{categoryLabel(data.speciality)}</span>
            </div>
          </div>
          {data.members?.length ? (
            <div className="list-grid compact">
              {data.members.map((member) => (
                <a className="piece-card" key={member.id} href={blogUrl(member.username)}>
                  <div className="piece-card-kicker">{member.role}</div>
                  <h2 className="piece-card-title">{usernameHandle(member.username)}</h2>
                  <p className="piece-card-excerpt">{member.contribution_count} contribuții</p>
                </a>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </PageShell>
  );
}

export default function ClubsRoute({ route }) {
  if (route.name === "club") return <ClubDetailView slug={route.slug} />;
  return <ClubsView />;
}
