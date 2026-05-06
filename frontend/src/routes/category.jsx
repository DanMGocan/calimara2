import { Fragment } from "react";
import { fetchCategory } from "../api/public.js";
import { PostCard } from "../app/content.jsx";
import { categoryLabel } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { ActionRow, AdSlot, PageShell, StatusPanel } from "../app/layout.jsx";
import { mainPath } from "../app/paths.js";

function CategoryView({ categoryKey }) {
  const { data, error, loading } = useAsync(() => fetchCategory(categoryKey), [categoryKey]);
  return (
    <PageShell
      kicker="categorie"
      title={data?.category_name ?? categoryLabel(categoryKey)}
      sub="Texte publicate în această categorie."
      side={
        <aside className="side-col">
          <div className="side-kicker">categorii</div>
          <div className="actions-group">
            <ActionRow number="01" label="Poezie" active={categoryKey === "poezie"} onClick={() => { window.location.href = mainPath("/categorie/poezie"); }} />
            <ActionRow number="02" label="Proză scurtă" active={categoryKey === "proza_scurta"} onClick={() => { window.location.href = mainPath("/categorie/proza_scurta"); }} />
          </div>
        </aside>
      }
    >
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca categoria">{error}</StatusPanel> : null}
      {data?.posts?.length ? (
        <div className="list-grid">
          {data.posts.map((post, index) => (
            <Fragment key={post.id}>
              <PostCard post={post} />
              {index === 1 ? <AdSlot placement="inline" /> : null}
            </Fragment>
          ))}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu există texte încă" /> : null}
    </PageShell>
  );
}

export default function CategoryRoute({ route }) {
  return <CategoryView categoryKey={route.categoryKey} />;
}
