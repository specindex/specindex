/**
 * How many pages a build should emit.
 *
 * THE PROBLEM. `next build` statically renders one page per project. A pull
 * request therefore rebuilds the entire site -- ~27,000 pages -- before it is
 * allowed to merge, taking 5-11 minutes. Because `build_and_preview` is a
 * required check on main, merging one PR invalidates every other open PR and
 * each needs another full build. Seven PRs were open on 2026-08-05 and four had
 * to be closed as stale regressions.
 *
 * AND IT GETS WORSE ON ITS OWN. The crawler adds projects continuously, and
 * every project is a page. Build time is currently a function of corpus size,
 * so it grows every day whether or not anyone touches the code. That is the
 * part worth fixing: not "the build is slow today" but "the build gets slower
 * forever".
 *
 * THE INSIGHT. Verifying that a template renders does NOT require rendering
 * every row behind it. Ten project pages exercise exactly the same component
 * tree, data shape, CSS and layout as 27,000 of them -- they differ only in
 * content. A preview build needs one page of each KIND, not one page per
 * record.
 *
 *   pull request  ->  ~10 pages per route  ->  seconds
 *   merge to main ->  every page           ->  the real site
 *
 * The Firebase preview link still works and is still clickable; two genuine
 * rendering defects were caught that way on 2026-08-05 (a location string
 * rendering as ", Georgia", and empty fact cards printing "Not reported"), and
 * both would have been caught just as well by ten pages.
 *
 * FAIL-SAFE BY DESIGN. Truncation happens only when preview mode is switched
 * on EXPLICITLY. Any unset, misspelled or unexpected value yields a full
 * build. A shortened production deploy would silently drop pages from the live
 * site and from search indexes -- far worse than a slow build -- so the
 * default must be the safe one, not the fast one.
 */

/** Pages per route in a preview build. Enough to exercise every template and
 *  catch a rendering defect; small enough to finish in seconds. */
export const PREVIEW_PAGE_LIMIT = 10;

/**
 * True only when this build is an explicit preview.
 *
 * SPECINDEX_PREVIEW_BUILD is set by .github/workflows/firebase-hosting-pull-request.yml.
 * GITHUB_EVENT_NAME === "pull_request" is a secondary signal so a PR build is
 * still truncated if someone adds a new workflow and forgets the flag.
 *
 * Note both checks are positive assertions of "this is a preview". There is
 * deliberately no "is this production" check whose failure could truncate a
 * real deploy.
 */
export function isPreviewBuild(): boolean {
  if (process.env.SPECINDEX_PREVIEW_BUILD === "1") return true;
  if (process.env.GITHUB_EVENT_NAME === "pull_request") return true;
  return false;
}

/**
 * Trim a static-params list for preview builds; return it untouched otherwise.
 *
 * Logs what it did, because a build that silently emits 10 pages instead of
 * 27,000 looks identical in the output to one that found only 10 projects --
 * and this repo has been bitten repeatedly by results that were quietly wrong
 * rather than loudly broken.
 */
export function scopeStaticParams<T>(params: T[], route: string): T[] {
  if (!isPreviewBuild() || params.length <= PREVIEW_PAGE_LIMIT) return params;
  console.log(
    `[build-scope] ${route}: preview build, rendering ${PREVIEW_PAGE_LIMIT} of ` +
      `${params.length} pages. Full set renders on main.`,
  );
  return params.slice(0, PREVIEW_PAGE_LIMIT);
}
