"""
Page 6 — Files

Upload and retrieve programme files of any type.
"""
import streamlit as st

st.set_page_config(page_title="Files - GSD Dashboard", layout="wide")

import pandas as pd

from auth.setup import require_auth, get_user_role, get_display_name, get_username
from auth.audit import log_action
from components.branding import inject_luxury_styles, render_sidebar_branding
from components.freshness import render_freshness_badges
from data.file_store import delete_upload, get_download_bytes, list_uploads, save_upload


require_auth()
inject_luxury_styles()

role = get_user_role()
name = get_display_name()
username = get_username() or name
render_sidebar_branding(name, role)

with st.sidebar:
    st.page_link("app.py",                            label="Home")
    st.page_link("pages/1_Timeline.py",               label="Timeline")
    st.page_link("pages/2_Stakeholder_Views.py",      label="Stakeholder Views")
    st.page_link("pages/3_Risk_Heat_Map.py",          label="Risk Heat Map")
    st.page_link("pages/4_Deliverables.py",           label="Deliverables")
    st.page_link("pages/5_KPI_Dashboard.py",          label="KPI Dashboard")
    st.page_link("pages/6_Files.py",                  label="Files")
    if role == "admin":
        st.page_link("pages/7_Admin.py",                  label="Admin")
    render_freshness_badges()

log_action("view_files", "page", "files")

st.markdown(
    '<div class="prog-title">Files</div>'
    '<div class="prog-sub">Upload supporting documents, spreadsheets, slide decks, text files, and other artefacts</div>',
    unsafe_allow_html=True,
)
st.divider()

if role in ("admin", "implementation"):
    st.subheader("Upload Files")
    uploads = st.file_uploader(
        "Choose one or more files",
        accept_multiple_files=True,
        type=None,
        help="Any file type is accepted. Streamlit's server upload limit still applies.",
    )

    if uploads:
        if st.button("Save uploads", width="stretch"):
            saved = []
            failed = []
            for upload in uploads:
                try:
                    record = save_upload(upload, username, role)
                    saved.append(record["name"])
                    log_action("upload_file", "file", record["stored_name"])
                except Exception as exc:
                    failed.append(f"{upload.name}: {exc}")
            if saved:
                st.success(f"Uploaded {len(saved)} file(s).")
            if failed:
                st.error("Some files could not be uploaded.")
                for message in failed:
                    st.caption(message)
            st.rerun()
else:
    st.info("File uploads are available to implementation users. Existing files are visible below.")

st.divider()
st.subheader("Uploaded Files")

files = list_uploads()
if not files:
    st.info("No files uploaded yet.")
else:
    table = pd.DataFrame(files)
    display = table.rename(columns={
        "name": "File",
        "size": "Size (bytes)",
        "content_type": "Type",
        "uploaded_by": "Uploaded By",
        "role": "Role",
        "uploaded_at": "Uploaded At",
    })
    visible_cols = [c for c in ["File", "Size (bytes)", "Type", "Uploaded By", "Role", "Uploaded At"] if c in display.columns]
    st.dataframe(display[visible_cols], width="stretch", hide_index=True)

    st.markdown("#### Download")
    options = {row["stored_name"]: row["name"] for row in files}
    selected = st.selectbox("Select a file", list(options.keys()), format_func=lambda key: options[key])
    data = get_download_bytes(selected)
    if data is None:
        st.warning("This file could not be loaded for download.")
    else:
        selected_row = next(row for row in files if row["stored_name"] == selected)
        st.download_button(
            "Download selected file",
            data=data,
            file_name=selected_row["name"],
            mime=selected_row.get("content_type") or "application/octet-stream",
            width="stretch",
        )

    if role in ("admin", "implementation"):
        st.markdown("#### Remove")
        confirm = st.checkbox(
            f"Confirm removal of {options[selected]}",
            key=f"confirm_delete_{selected}",
        )
        if st.button("Remove selected file", disabled=not confirm, width="stretch"):
            try:
                delete_upload(selected)
                log_action("delete_file", "file", selected)
                st.success("File removed.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not remove file: {exc}")
