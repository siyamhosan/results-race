# Can we get per-subject marks from the Bangladesh board result sites?

## Outcome (confirmed with real responses)

Marks **are** public for HSC 2026: a real `/v2/getres` answer carried `showmarks: 1` and `display_details` entries like
`101-102:171=A+` (two papers sharing one code, total, then grade), plus `tot_full`, `conv_1000` and `sub4th`.
SSC 2024 answers had `showmarks: 0` and grades only. The sheet now reads and shows the marks (`card.parse_entry`).
The sections below were written before this was confirmed and say it was unknown.


Researched 2026-10-31. Method: loaded the pages in a normal headless Chromium (a JS "Verifying you are not a robot"
interstitial blocks plain curl; a normal browser passes it by itself, nothing was bypassed), read the page's
inline JavaScript and form controls. No captcha was solved and **no lookup was submitted**, so no real response
body was seen. Labels: **observed** = seen in fetched page/JS/DOM; **inferred** = deduced, not seen.

Sources (all fetched 2026-10-31): `https://eboardresults.com/v2/home`, `https://result.rajshahiboard.gov.bd/v2/home`,
`https://www.educationboardresults.gov.bd/v2/home`. "Script L<n>" below = line n of the 24,037-byte inline `<script>`
(the third inline script on /v2/home, the one starting `$(document).ready(function(){var captcha_dirty=...`), as
exported with the line breaks the site ships (minified, so lines are long). That script is byte-identical in size on
all three mirrors (observed: 173 / 1009 / 24037 byte inline scripts on each).

## Short answer

The site's result page is **built to show marks, but only when the server's JSON says so** (`showmarks == 1`).
Whether the real answer ever sets it for current SSC/HSC lookups is **not known** without one real lookup (see the
checklist at the end). Nothing in the page, form or JS offers a separate marks endpoint, marksheet, or transcript
for the public.

## 1. Does a response field already carry marks?

- The renderer for result_type 1 (and 8) is `show_stud_result(resp, exam, year)`. (observed, Script L37 `get_result_method`:
  `case '1': case '8': show_stud_result`.)
- It takes the subject lines from `res.display_details` (title "Subject-wise Grade/Marks") and
  `res.display_details_ca` (title "...for Continuous Assessment"), plus optional `res.log_display_details[_ca]`
  (old values after re-scrutiny). (observed, Script L77-L80)
- Each line is split on `,`, then `code:rest`, then `rest` on `=`. The last `=` part is the grade; if there are
  2 parts it is `total=grade`; if 3 parts it is `detail=total=grade`. (observed, Script L93)
  So the wire format the page can parse is:
  - `101:A+` -> grade only (what the repo sees today)
  - `101:78=A+` -> total mark + grade
  - `101:50+0+28=78=A+` -> theory+practical+MCQ = total = grade
  - several papers of one subject are joined with `-` in the detail part (`mrks_dtls.split('-')`, then `split('+')`
    into t/p/m). (observed, Script L95)
- Marks columns (Theory, Practical, MCQ, Total) are drawn **only if `resp.showmarks==1`**, and the three split columns
  only if also `resp.totalonly!=1`; with `totalonly==1` just a "Marks" total column. (observed, Script L84-L85, L89, L95, L100)
  `showmarks`, `totalonly`, `hidefailed` are top-level keys of the JSON, next to `status`/`res` (observed as names
  read by the JS; their server values were **not** observed).
- `hidefailed==1` blanks the marks of an `F` subject. (observed, Script L93-L94)
- The grade column header switches on year: `grd_start_config = {"ssc":2001,"hsc":2003,"jsc":2010}`; for
  `year >= that` it says "Grade", for earlier years "Marks". (observed: values in the first inline script/page head,
  header logic Script L88). Inferred: for SSC before 2001, HSC before 2003, the `display_details` value is a mark,
  not a letter. Not relevant for a 2026 HSC.
- Inferred (not observed): since the repo's samples are `code:A+` with no `=`, `showmarks` is probably 0 or absent
  for current exams, i.e. the server withholds marks. Nothing in the client contradicts or confirms this.
- Other fields the JS reads from `res`: `board_name, session, stud_group, stud_type, stud_sex/sex, res_detail
  (shown as "Passed" if `P`, else raw, e.g. `GPA=5.00`), dob, inst_name/eiin, fname, mname, name, roll_no, regno`;
  top-level `notice, sub_details, sub (URL to resolve subject names), eiin_url, stat_url, extra`. No field named
  marks/number/total in `res` is read. (observed, Script L69-L100, L38)
- Subject names come from `sub_details` [{SUB_CODE, SUB_NAME}] or by GET of `resp.sub`. (observed, Script L100+, `display_sub`)

## 2. Endpoints, params, auth

All observed from the page's config script and form:

| Item | Value | Source |
|---|---|---|
| Result | `POST getres` (relative to `/v2/`, so `/v2/getres`) | `result_svc_url='getres'`, `result_svc_method='post'` (config inline script) |
| Captcha | `GET /v2/captcha` | `captcha_svc_url` (same) |
| Form fields | `board, exam, year, result_type, roll, reg, eiin, dcode, ccode, captcha` | form `name=` attributes in DOM |
| Lists | `GET /v2/list?id=dlist` / `clist` (district / centre) | Script L28-L33 |
| PDF | `pdl` (download), only for types 2,4,5 | `pdf_dl_url`, Script L8 |
| Tree / table UI | `btreeui`, `btblui` | config script |
| Testimonial CSS | `/app/stud/allcss/testimonial.css` (type 3 only, Chrome-only check) | config script, Script L46 |
| Extra (optional) | `extsvc` object may redirect a given exam+year to another URL/captcha | Script L35; **undefined on all 3 mirrors (observed)** |

- Required inputs per type (Script L8-L14): type 1 = roll+reg; 2 = eiin; 3 = roll; 4 = dcode+ccode;
  5 = dcode; 6 = eiin; 7 = none; 8 = roll+reg. Captcha is required whenever `captcha_url` is non-empty (always, here).
- A 419 response means "refresh to verify you are not a robot": the JS-challenge cookie must be present (observed, Script L47).
- No login or extra token for individual results is visible. No separate marks parameter exists in the form.

## 3. Which mirror / which result_type?

`result_type` options actually offered in the dropdown (observed, DOM `#result_type`):

| Mirror | Types offered |
|---|---|
| eboardresults.com | 1 Individual/Detailed, 2 Institution, 6 Institution Analytics, 7 Board Analytics |
| result.rajshahiboard.gov.bd | same four; only board `rajshahi`, exams jsc/ssc/hsc |
| www.educationboardresults.gov.bd | only 1 and 2 |

- Types 3 (testimonial), 4 (centre), 5 (district) and 8 (a second individual view, same renderer as 1) exist in the JS but
  are **not offered** on any of the three mirrors (observed). Whether the server answers if posted by hand is unknown
  (inferred: likely rejected; not tried, to avoid abusing the service).
- Type 2 (institution result): the server returns ready-made HTML in `resp.extra.content` (Script L52-L55). Could contain
  anything, including per-student rows; unknown. Needs `eiin` + captcha. Not tested.
- Types 6/7 are chart/statistics pages (Google Charts), not per-student.
- Since the front-end script is the same size on all three, any mirror renders marks identically; what differs is only the
  server's data (inferred).

## 4. Other official sites

- `https://www.educationboardresults.gov.bd/regular/` -> **403 Forbidden** nginx (observed in browser).
- `https://app.rajshahiboard.gov.bd/eservice` -> **403 Forbidden** nginx 1.19.4 (observed).
- `https://rajshahieducationboard.gov.bd/` (portal): result-related links seen: re-scrutiny
  `https://rescrutiny.eduboardresults.gov.bd/` (page showed "system maintenance"; text says HSC 2026 re-scrutiny/re-evaluation
  applications open from 1 November 2026; observed), admit-card print
  `http://app.rajshahiboard.gov.bd/eservice/archive/admit.php?type=public` and registration card print `.../reg.php?type=public`
  (links observed, not opened). None is a marks lookup.
- The portal's e-service list (`/pages/internal-eservices`) is about internal staff services (examiner appointment letters, etc.).
- Not checked: institution-login (EIIN) portals, other boards' own sites (links listed on the portal, e.g. dhakaeducationboard.portal.gov.bd,
  bteb.gov.bd, bmeb.gov.bd). Marks for re-scrutiny are, as far as the above shows, only via the school/board channel (inferred).

## 5. Verdict

- **No public marks API exists** that I could find; no extra endpoint, marksheet, transcript or number-wise lookup is linked.
- **The only candidate is `/v2/getres` itself**, whose `display_details` can carry `code:detail=total=grade` and whose flag
  `showmarks` turns the columns on. Whether current HSC/SSC answers use it is **unverified** (needs one human lookup).
- Likely outcome (inferred): grades only, which matches how the repo reads `display_details` today.

## 6. How the human confirms (one lookup)

1. Open `https://eboardresults.com/v2/home` in Chrome (let the "Verifying you are not a robot" page finish).
2. Open DevTools -> Network, tick "Preserve log", filter `getres`.
3. Enter the sample id: exam `hsc`, year `2026` (as in `results-race.toml`), board = that student's board, Result type
   `Individual/Detailed Result`, the sample roll and registration, type the captcha, Submit.
4. Click the `getres` request -> Response. Check:
   - Top-level keys: is there `"showmarks"` (and `1`)? `"totalonly"`, `"hidefailed"`?
   - In `res.display_details`: any `=` in an entry (e.g. `101:78=A+`)? If only `101:A+`, marks are not served.
   - Any other `res` key you did not see in `demo.py` (e.g. `log_display_details`, `extra`)?
5. Repeat step 3 on `www.educationboardresults.gov.bd/v2/home` only if the first shows no marks (the data should be the same;
   expected same result). Paste the JSON with name/roll/reg removed, or just the key names and one `display_details` string.
6. If marks do appear: parse each `display_details` entry as `code:` + `[detail=]total=grade` (split on `=`, last part is the grade),
   and detail as papers split by `-`, components by `+` (theory+practical+MCQ).

## Follow-up: apps and district sites

Researched 2026-10-31 (about 04:30-05:00 UTC). Method: WebSearch, plain `curl` GETs of public landing pages and public JS
bundles, Google Play listing pages fetched as static HTML. No captcha was loaded-and-solved or submitted, no lookup was
POSTed, no app was decompiled or run, nothing behind a login was touched. Labels: **observed** = seen in a page/JS/HTTP
response I fetched; **claimed** = a third party says so (SEO blog, app listing), not checked; **inferred** = my deduction.
Note: the HSC 2026 result was not yet live when I looked (BISE Chattogram's own HSC page was still a countdown to
`2026-10-31 11:00` Bangladesh time, observed), so nothing below was tested against a real HSC 2026 answer.

### Short answer

- **No board publishes a separate marks service.** Every board result page I could read is either the shared `/v2`
  "eboardresults" software (grades by default, marks only if `showmarks==1`) or a board's own page that I could not see
  past its countdown. The mobile apps do not have a private marks feed that I can find: their own Play text says they
  use the boards' public result service, plus captcha ("Complete verification"). (observed listing text; mechanism inferred)
- **The one place marks are verifiably wired in outside the `/v2` software is BTEB** (technical board,
  `result.bteb.gov.bd`): its public JSON API has a `marksVisible` flag that adds "Full Marks / Obtained Marks" columns.
  (observed, bundle JS). That covers technical-board HSC (BM/Vocational) and diplomas, not the general HSC/SSC boards.
- Many "marksheet with number" web sites and apps exist, and **all are unofficial** (own disclaimers or non-`.gov.bd`
  domains). Their marks claims are marketing until a real response shows `showmarks:1`.
- I found **no primary-source statement** (board notice, ministry circular) either promising or forbidding marks online.
  Third-party blogs say, without evidence, that marks show "for passed subjects" and sometimes appear hours after the
  grade sheet (claimed; see below). That would fit the server toggling `showmarks` after publication (inferred).

### 1. Apps (Google Play listings, fetched as static HTML)

Source for all rows: `https://play.google.com/store/apps/details?id=<package>&hl=en`, page text (`og:description` and
`itemprop="description"`), and the Play search page `https://play.google.com/store/search?q=ssc%20hsc%20result%20bangladesh&c=apps`.

| App (package) | What the listing says (observed text) | Marks? | Data source / disclaimer |
|---|---|---|---|
| Folafol (`com.allresults.techinternal`), site `folafol.app` | "HSC marksheet with subject grades, GPA and board results"; long text: "full marksheet — subject grades, marks and GPA"; "Three official result servers with live status. If one is busy, switch to another"; "Folafol keeps a copy of your result" | Claimed ("marks"); the short blurb says only "grades" | "Folafol is an independent app. It is not affiliated with ... any education board ... Results come from the boards' own public result service." No captcha mentioned. |
| HSC Result 2026 (মার্কশীট সহ), AppHood (`com.apphood.sschsc`), privacy policy at `app.sschsc.com/privacy-policy/` | "check ... results by roll and registration number ... with full marksheet" | Claimed | No data-source statement seen |
| Result Hub BD (`com.sscresultbd.fastcheck`) | "Subject-wise marksheet & GPA"; "Complete verification and tap Get Result" | Claimed | "not affiliated with or endorsed by any government organization or education board. It only presents publicly available information"; names `http://www.educationboardresults.gov.bd` as official |
| Others in the Play search (AppHood "Result App", "All Exam Result 2026", Codesphere "HSC/SSC Result - মার্কশিটসহ", Niloy Things, etc.) | Titles say "মার্কশিটসহ" | Claimed | Not opened |

Reading: (a) "Three official result servers" most plausibly means the same `/v2` mirrors we already know
(eboardresults.com, educationboardresults.gov.bd, a board mirror) (inferred); (b) "Complete verification" = the same
captcha, so the apps are thin clients over the public result service, not a way around it (inferred from Result Hub's
wording). (c) "Keeps a copy of your result" means Folafol caches responses after a human lookup (claimed).
I did not open the apps or sniff their traffic, so which host each calls is **unknown**. Note the apps being on
Play is not an endorsement by any board; none is a board app. A blog (secondary) mentions an app named
"Education Board Results" / "BD result" as Ministry-made (claimed, SEO page, unverified, not found in the Play search).

### 2. Third-party web clients that mimic the board page

`https://eboardresultsapp.com/result/ssc/` (+ `sscresults.js`) and `https://result.bangladeshgov.org/`,
`https://result.kgpurhs.edu.bd/` (all observed, static HTML/JS):

- **Not official** (observed): domains are not `.gov.bd`/`.edu`-board; `bangladeshgov.org` is a WordPress site behind
  Cloudflare (whois: registrar Spaceship, record updated 2026-08-12); `result.kgpurhs.edu.bd` is a school-looking
  hostname whose page declares `canonical = https://eboardresultsapp.com`; the pages say "100% Official" in text while
  also saying "official board websites publish results separately". Treat as SEO mirrors/proxies run by third parties.
- Their JS is a copy of the official `/v2` renderer: same `display_details` parsing, `showmarks==1`, `totalonly`,
  `log_display_details`, "Subject-wise Grade/Marks". So it does not prove marks are served; it proves the clone
  authors copied the official logic. (observed)
- Old-API request shape they use: `POST https://result.bangladeshgov.org/result` (or
  `https://result.kgpurhs.edu.bd/result` for institution type 2), `application/x-www-form-urlencoded` with the same
  form fields as `/v2/getres`, `credentials: include`; captcha `GET <base>/captcha?t=<ms>`; institution PDFs
  `GET https://result.kgpurhs.edu.bd/pdl?name=<file>`. Response is checked as `resp.status === 1` = error with `resp.msg`
  (note: opposite polarity to a success). (observed)
- **SSC 2026-only JSON API** (observed in the same JS, host did not resolve from my machine at 04:36 UTC, so possibly
  gone): captcha `GET https://api.bangladeshgov.org/ssc2026/captcha` -> `{imageBase64, hash, timestamp}`; result
  `POST https://api.bangladeshgov.org/ssc2026` JSON `{rollNo, regNo, boardId (dhaka 10, comilla 11, rajshahi 12, jessore 13,
  chittagong 14, barisal 15, sylhet 16, dinajpur 17, madrasah 18, tec 19, mymensingh 21), passYear, captchaText, hash,
  timestamp}`; reply `{status:'success', data:{studentInfo:{rollNo,regNo,name,fatherName,motherName,groupName,session,
  result,gpa,instituteName,...}, subjects:[{marks, grade, isContinuousAssessment, ...}]}}`. The code shows a "Marks" column
  only if some `subjects[].marks` is non-empty. This is a third party's own backend; I cannot say whether it forwards to a
  board. The page itself says marks "depend on your board's permission to show detailed marks" (claimed by the site),
  which matches `showmarks` being a per-board/per-exam switch (inferred).
- Legality: clearly **unofficial**; whether they scrape or proxy a board is **unknown**. Sending student rolls/regs and
  captcha answers to such hosts hands data to unknown operators. Do not route our tool through them.

### 3. Board and technical/madrasah sites (landing pages fetched statically)

| Site | What I saw (observed) | Marks? | Captcha/login |
|---|---|---|---|
| Dhaka `dhakaeducationboard.gov.bd/site/` | no result link in static HTML | unknown | unknown |
| Chattogram `hscresult.bise-ctg.gov.bd/h22_31_x1_26/individual/` and `/h22_31_x1_26/` ("Institute wise HSC Result 2026") | board's **own** result site (links from `web.bise-ctg.gov.bd`); at fetch time only a countdown to 31 Oct 2026 11:00, no form, so request shape unseen. Also "Online CA/Practical Marks" at `practical.bise-ctg.gov.bd` is for institutions to submit marks to the board, not a student lookup | unknown until published | unknown |
| Barishal `result.barisalboard.gov.bd` (Vite SPA, 494-byte shell), `barisalboard.gov.bd/hscresult/login`, `/sscresult/login` | own app; the `/…result/login` pages are institution/centre logins | unknown | login for institution pages (observed URL names only, not opened) |
| Sylhet `result.sylhetboard.gov.bd` | same JS-challenge + `/v2/home` software as eboardresults (observed redirect `…/_challenge-engine?goto=/v2/home`); `esheba.sylhetboard.gov.bd/publicResult/` has `jsc.php`, `rescrutiny.php` links | same as `/v2` | same as `/v2` |
| Dinajpur | menu "ফলাফল" links to `https://eboardresults.com/app/stud/` | same as `/v2` | same |
| Madrasah `ebmeb.gov.bd/erps_entry_forms/disp_res.php?exam=alm&year=2026` (linked from bmeb.gov.bd) | behind the same JS challenge; "রেজাল্ট আর্কাইভ" links to `www.educationboardresults.gov.bd` | unknown | unknown |
| Mymensingh | JS challenge page on the root | unknown | unknown |
| Jashore, Cumilla, Rajshahi | Jashore redirected to `www.`; Cumilla did not respond; Rajshahi covered in the first pass (`result.rajshahiboard.gov.bd/v2/home`, `/eservice` = 403) | see earlier sections | |
| **BTEB** `https://result.bteb.gov.bd/result-search` (linked from `bteb.gov.bd`; notice about HSC BM/Vocational/Diploma in Commerce 2nd-year final 2026) | React app; public API under `/api/public`: `GET /captcha` (returns a token; the on-screen check is a small arithmetic sum), `GET /curriculums`, `POST /result` JSON `{curriculumCode, rollNo, regNo, semester, examYear, captchaToken, captchaAnswer}` (roll/reg "six or ten digits"); error code `CAPTCHA_INVALID`; result `data.semesters[]` with subjects, GPA; **`marksVisible === true` adds "Full Marks" and "Obtained Marks" columns** (observed in `/assets/result-peia2evc.js`) | **Yes, conditionally**, technical board only | Captcha required |

Most other board hostnames I tried either sit behind the same bot-challenge or were not reachable. The secondary claim
that "some boards post detailed subject marks a little after the grade sheet" and that SMS gives only grade/GPA comes
from blogs (`bdservicerules.info/education-board-result/`, `educatebd.com/?p=1343`): **claimed, no primary source**.

### 4. SMS / Teletalk

Observed in primary-ish news: TBS "Here's how you can check SSC 2024 results" (`tbsnews.net/bangladesh/education/heres-how-you-can-check-ssc-2024-results-848721`)
and Prothom Alo (`en.prothomalo.com/youth/education/ocim3mk6x3`): SMS to **16222**, format `SSC <first 3 letters of board> <roll> <year>`
(e.g. `SSC DHA 123456 2024`); both articles say nothing about marks. Third-party pages say the reply has per-subject
**grades and GPA**, not marks (claimed). No marks via SMS found. (Not tested, SMS costs money and was out of scope.)
Both articles also say institutions can download a result sheet by board + EIIN (the `/v2` type 2), which third-party
pages describe as a PDF with name, roll, GPA, pass/fail (claimed; contents unverified, still the best unexplored lead for
marks because the server returns ready-made HTML/PDF).

### 5. Old vs current exams

- Observed in the first pass: the page header shows "Marks" instead of "Grade" for SSC before 2001 / HSC before 2003, so
  **old** exams are marks by construction there. For current SSC/HSC no source shows marks; the only hint of current marks
  is the SSC 2026 JSON schema above (a third party's client with a `marks` field) and Play-store marketing (claimed).
- Nothing found for SSC 2024 specifically beyond SEO text; no primary source.

### 6. Legality / terms

- No terms-of-use or robots notice was found on the pages I fetched (the board pages show only the bot challenge).
  I did not find any board statement permitting or banning automated lookups. **Inferred risk:** automated bulk lookups
  against a captcha-gated government service may breach site terms and the board's anti-bot control; the captcha itself
  is the control, so a human must type it, one student at a time, at a gentle rate.
- Clearly unofficial: Folafol, AppHood, Result Hub BD (own disclaimers), `eboardresultsapp.com`,
  `bangladeshgov.org`, `kgpurhs.edu.bd` mirror, `allresultbd.com`, `ssc.results.com.bd`, and similar SEO sites.
  Official domains seen: `educationboardresults.gov.bd`, `eboardresults.com` (linked from the Dinajpur board's own menu and
  described as the Education Ministry's alternative site by a blog), `result.rajshahiboard.gov.bd`, `result.sylhetboard.gov.bd`,
  `hscresult.bise-ctg.gov.bd`, `result.barisalboard.gov.bd`, `result.bteb.gov.bd`, `ebmeb.gov.bd`.

### 7. Most promising route (human types the captcha)

1. **Do the one lookup already described in section 6 above** on `https://eboardresults.com/v2/home` (the same server
   family every board mirror and, as far as I can tell, the apps' "official servers" use), but now also record
   `showmarks`, `totalonly`, `hidefailed`, and whether `display_details` contains `=`. If marks are served, our existing
   `/v2/getres` flow gets them with a one-line parser change (`code:[detail=]total=grade`); no new host needed.
2. If that shows grades only, **repeat once on the student's own board site after publication** (Chattogram
   `hscresult.bise-ctg.gov.bd/h22_31_x1_26/individual/` if the student is Chattogram; Barishal `result.barisalboard.gov.bd`),
   since those boards run their own software and may serve marks. Capture the request in DevTools; the request shape is unseen.
3. Next lead: type 2 institution result (EIIN + captcha) and look at the `extra.content` HTML for marks.
4. Do not use third-party "marksheet with number" hosts or app backends.
