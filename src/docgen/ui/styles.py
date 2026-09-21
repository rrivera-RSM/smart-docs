import streamlit as st

APP_CSS = """
<style>
  :root {
    --sd-blue: #009cde;
    --sd-blue-dark: #007eb4;
    --sd-green: #3f9c35;
    --sd-midnight: #00153d;
    --sd-slate-700: #334155;
    --sd-slate-500: #64748b;
    --sd-slate-300: #cbd5e1;
    --sd-slate-200: #e2e8f0;
    --sd-slate-100: #f1f5f9;
    --sd-slate-50: #f8fafc;
    --sd-radius: 14px;
    --sd-shadow: 0 12px 32px rgba(0, 21, 61, 0.07);
  }

  html, body, [class*="css"] {
    font-family: Arial, "Helvetica Neue", Helvetica, sans-serif;
  }

  .stApp {
    color: var(--sd-midnight);
    background:
      radial-gradient(circle at 88% 0%, rgba(0, 156, 222, 0.10), transparent 28rem),
      linear-gradient(180deg, #ffffff 0%, #f8fafc 38%, #f1f5f9 100%);
  }

  [data-testid="stHeader"] {
    background: transparent;
  }

  [data-testid="stMainBlockContainer"] {
    max-width: 1180px;
    padding-top: 2.4rem;
    padding-bottom: 2.5rem;
  }

  #MainMenu, footer {
    visibility: hidden;
  }

  .sd-brandbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 2.25rem;
  }

  .sd-brandbar__logo {
    width: 120px;
    height: 44px;
    object-fit: contain;
    object-position: left center;
  }

  .sd-brandbar__product {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .sd-brandbar__divider {
    width: 1px;
    height: 30px;
    background: var(--sd-slate-200);
  }

  .sd-brandbar__name {
    color: var(--sd-midnight);
    font-size: 0.92rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .sd-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 7px 11px;
    border: 1px solid rgba(0, 156, 222, 0.22);
    border-radius: 999px;
    color: #006c9b;
    background: rgba(0, 156, 222, 0.07);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .sd-badge__dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--sd-blue);
    box-shadow: 0 0 0 4px rgba(0, 156, 222, 0.12);
  }

  .sd-hero {
    position: relative;
    overflow: hidden;
    padding: 2rem 2.1rem;
    margin-bottom: 1.35rem;
    border: 1px solid rgba(0, 21, 61, 0.08);
    border-radius: 20px;
    color: white;
    background:
      radial-gradient(circle at 92% 20%, rgba(0, 156, 222, 0.42), transparent 24rem),
      linear-gradient(126deg, #00153d 0%, #072758 72%, #064571 100%);
    box-shadow: 0 18px 42px rgba(0, 21, 61, 0.16);
  }

  .sd-hero::after {
    content: "";
    position: absolute;
    right: -52px;
    bottom: -82px;
    width: 240px;
    height: 240px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 50%;
    box-shadow:
      0 0 0 30px rgba(255, 255, 255, 0.035),
      0 0 0 70px rgba(255, 255, 255, 0.025);
  }

  .sd-hero__eyebrow {
    position: relative;
    z-index: 1;
    margin: 0 0 0.6rem;
    color: #79d7ff;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.13em;
    text-transform: uppercase;
  }

  .sd-hero h1 {
    position: relative;
    z-index: 1;
    max-width: 720px;
    margin: 0;
    color: white;
    font-size: clamp(2rem, 4vw, 3.15rem);
    font-weight: 750;
    line-height: 1.02;
    letter-spacing: -0.045em;
  }

  .sd-hero p {
    position: relative;
    z-index: 1;
    max-width: 650px;
    margin: 1rem 0 0;
    color: #cbd8ea;
    font-size: 0.98rem;
    line-height: 1.65;
  }

  .sd-stepper {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.65rem;
    margin: 0 0 1.35rem;
  }

  .sd-step {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
    padding: 0.72rem 0.8rem;
    border: 1px solid var(--sd-slate-200);
    border-radius: 12px;
    color: var(--sd-slate-500);
    background: rgba(255, 255, 255, 0.74);
  }

  .sd-step--active {
    border-color: rgba(0, 156, 222, 0.4);
    color: var(--sd-midnight);
    background: rgba(0, 156, 222, 0.08);
    box-shadow: inset 0 -2px 0 var(--sd-blue);
  }

  .sd-step--done {
    color: #245f20;
    border-color: rgba(63, 156, 53, 0.28);
    background: rgba(63, 156, 53, 0.07);
  }

  .sd-step__number {
    display: grid;
    flex: 0 0 28px;
    width: 28px;
    height: 28px;
    place-items: center;
    border-radius: 9px;
    color: var(--sd-midnight);
    background: var(--sd-slate-100);
    font-size: 0.73rem;
    font-weight: 800;
  }

  .sd-step--active .sd-step__number {
    color: white;
    background: var(--sd-blue);
  }

  .sd-step--done .sd-step__number {
    color: white;
    background: var(--sd-green);
  }

  .sd-step__label {
    overflow: hidden;
    font-size: 0.78rem;
    font-weight: 700;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  [data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--sd-slate-200);
    border-radius: var(--sd-radius);
    background: rgba(255, 255, 255, 0.86);
    box-shadow: 0 1px 2px rgba(0, 21, 61, 0.025);
  }

  [data-testid="stVerticalBlockBorderWrapper"]:has(.sd-primary-card) {
    box-shadow: var(--sd-shadow);
  }

  .sd-primary-card, .sd-side-card, .sd-result-card {
    display: none;
  }

  .sd-section-heading {
    margin-bottom: 0.2rem;
  }

  .sd-section-heading__eyebrow {
    margin: 0 0 0.28rem;
    color: var(--sd-blue-dark);
    font-size: 0.69rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .sd-section-heading h2 {
    margin: 0;
    color: var(--sd-midnight);
    font-size: 1.15rem;
    font-weight: 750;
    letter-spacing: -0.02em;
  }

  .sd-section-heading p {
    margin: 0.42rem 0 0;
    color: var(--sd-slate-500);
    font-size: 0.84rem;
    line-height: 1.5;
  }

  [data-testid="stFileUploaderDropzone"] {
    min-height: 160px;
    padding: 1.1rem;
    border: 1.5px dashed #9fb4c8;
    border-radius: 12px;
    background: var(--sd-slate-50);
    transition: border-color 160ms ease, background 160ms ease;
  }

  [data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--sd-blue);
    background: rgba(0, 156, 222, 0.045);
  }

  [data-testid="stFileUploaderDropzoneInstructions"] > div > span {
    color: var(--sd-midnight);
    font-weight: 700;
  }

  .sd-file-meta {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 12px;
    padding: 0.8rem;
    margin-top: 0.25rem;
    border: 1px solid var(--sd-slate-200);
    border-radius: 11px;
    background: var(--sd-slate-50);
  }

  .sd-file-meta__icon {
    display: grid;
    width: 38px;
    height: 38px;
    place-items: center;
    border-radius: 10px;
    color: #006c9b;
    background: rgba(0, 156, 222, 0.11);
    font-size: 0.68rem;
    font-weight: 900;
  }

  .sd-file-meta__name {
    overflow: hidden;
    color: var(--sd-midnight);
    font-size: 0.82rem;
    font-weight: 700;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sd-file-meta__size {
    margin-top: 2px;
    color: var(--sd-slate-500);
    font-size: 0.72rem;
  }

  .sd-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #2f7c28;
    font-size: 0.71rem;
    font-weight: 800;
  }

  .sd-status::before {
    content: "";
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--sd-green);
  }

  .sd-feature-list {
    display: grid;
    gap: 0.85rem;
    margin-top: 0.45rem;
  }

  .sd-feature {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 11px;
    align-items: start;
  }

  .sd-feature__number {
    display: grid;
    width: 30px;
    height: 30px;
    place-items: center;
    border-radius: 9px;
    color: var(--sd-blue-dark);
    background: rgba(0, 156, 222, 0.09);
    font-size: 0.72rem;
    font-weight: 850;
  }

  .sd-feature strong {
    display: block;
    margin: 1px 0 3px;
    color: var(--sd-midnight);
    font-size: 0.8rem;
  }

  .sd-feature p {
    margin: 0;
    color: var(--sd-slate-500);
    font-size: 0.75rem;
    line-height: 1.45;
  }

  .sd-callout {
    padding: 1rem 1.05rem;
    border: 1px solid rgba(217, 119, 6, 0.25);
    border-radius: 12px;
    background: rgba(245, 158, 11, 0.07);
  }

  .sd-callout--success {
    border-color: rgba(63, 156, 53, 0.25);
    background: rgba(63, 156, 53, 0.07);
  }

  .sd-callout__title {
    margin: 0;
    color: var(--sd-midnight);
    font-size: 0.88rem;
    font-weight: 800;
  }

  .sd-callout__text {
    margin: 0.35rem 0 0;
    color: var(--sd-slate-700);
    font-size: 0.79rem;
    line-height: 1.5;
  }

  .sd-variable-list {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 0.25rem;
  }

  .sd-variable {
    padding: 5px 8px;
    border: 1px solid rgba(0, 156, 222, 0.18);
    border-radius: 7px;
    color: #006c9b;
    background: rgba(0, 156, 222, 0.06);
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.69rem;
    font-weight: 650;
  }

  .sd-result {
    padding: 1.15rem;
    border: 1px solid rgba(63, 156, 53, 0.25);
    border-radius: 12px;
    background:
      linear-gradient(135deg, rgba(63, 156, 53, 0.10), rgba(255, 255, 255, 0.9) 68%);
  }

  .sd-result h3 {
    margin: 0;
    color: #245f20;
    font-size: 1rem;
    font-weight: 800;
  }

  .sd-result p {
    margin: 0.35rem 0 0;
    color: var(--sd-slate-700);
    font-size: 0.79rem;
  }

  .stTextInput label p, .stTextArea label p {
    color: var(--sd-midnight);
    font-size: 0.79rem;
    font-weight: 700;
  }

  .stTextInput input, .stTextArea textarea {
    border-color: var(--sd-slate-300);
    border-radius: 10px;
    color: var(--sd-midnight);
    background: white;
  }

  .stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--sd-blue);
    box-shadow: 0 0 0 3px rgba(0, 156, 222, 0.14);
  }

  .stButton button, .stDownloadButton button, .stFormSubmitButton button {
    min-height: 2.7rem;
    border-radius: 10px;
    font-weight: 750;
    transition: transform 140ms ease, box-shadow 140ms ease, background 140ms ease;
  }

  .stButton button[kind="primary"],
  .stFormSubmitButton button[kind="primary"] {
    border-color: var(--sd-blue);
    color: white;
    background: var(--sd-blue);
    box-shadow: 0 7px 16px rgba(0, 156, 222, 0.18);
  }

  .stButton button:hover, .stDownloadButton button:hover,
  .stFormSubmitButton button:hover {
    transform: translateY(-1px);
  }

  details {
    border-color: var(--sd-slate-200) !important;
    border-radius: 10px !important;
    background: var(--sd-slate-50) !important;
  }

  .sd-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding-top: 1.5rem;
    color: var(--sd-slate-500);
    font-size: 0.7rem;
  }

  .sd-footer__security {
    display: flex;
    align-items: center;
    gap: 7px;
  }

  .sd-footer__security::before {
    content: "";
    width: 7px;
    height: 7px;
    border: 2px solid var(--sd-green);
    border-radius: 50%;
  }

  @media (max-width: 760px) {
    [data-testid="stMainBlockContainer"] {
      padding-top: 1.2rem;
    }

    .sd-brandbar {
      margin-bottom: 1.2rem;
    }

    .sd-badge {
      display: none;
    }

    .sd-hero {
      padding: 1.5rem 1.25rem;
      border-radius: 16px;
    }

    .sd-stepper {
      grid-template-columns: repeat(2, 1fr);
    }

    .sd-step__label {
      white-space: normal;
    }

    .sd-file-meta {
      grid-template-columns: auto minmax(0, 1fr);
    }

    .sd-status {
      grid-column: 2;
    }

    .sd-footer {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
"""


def inject_styles() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)
