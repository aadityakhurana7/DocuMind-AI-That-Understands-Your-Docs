import streamlit as st
import os
import shutil
from utils.save_docs import save_docs_to_vectordb
from utils.session_state import initialize_session_state_variables
from utils.prepare_vectordb import get_vectorstore
from utils.chatbot import chat

class ChatApp:
    """
    A Streamlit application for chatting with PDF documents

    This class encapsulates the functionality for uploading PDF documents, processing them,
    and enabling users to chat with the documents using a chatbot. It handles the initialization
    of Streamlit configurations and session state variables, as well as the frontend for document
    upload and chat interaction
    """
    def __init__(self):
        """
        Initializes the ChatApp class

        This method ensures the existence of the 'docs' folder, sets Streamlit page configurations,
        and initializes session state variables
        """
        # Ensure the docs folder exists
        if not os.path.exists("docs"):
            os.makedirs("docs")

        # Configurations and session state initialization
        st.set_page_config(page_title="DocuMind")
        st.title("DocuMind")
        initialize_session_state_variables(st)
        self.docs_files = st.session_state.processed_documents

    def run(self):
        """
        Runs the Streamlit app for chatting with PDFs

        This method handles the frontend for document upload, unlocks the chat when documents are uploaded,
        and locks the chat until documents are uploaded
        """
        upload_docs = os.listdir("docs")
        # Keep docs list in sync every run (handles clear/reset cases)
        self.docs_files = upload_docs
        # Sidebar frontend for document upload
        with st.sidebar:
            st.subheader("Your documents")
            if upload_docs:
                st.write("Uploaded Documents:")
                st.text(", ".join(upload_docs))
            else:
                st.info("No documents uploaded yet.")
            st.subheader("Upload PDF documents")
            pdf_docs = st.file_uploader("Select a PDF document and click on 'Process'", type=['pdf'], accept_multiple_files=True)
            if pdf_docs:
                save_docs_to_vectordb(pdf_docs, upload_docs)

            st.subheader("Maintenance")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Clear chat"):
                    st.session_state.chat_history = []
                    st.success("Chat history cleared.")
            with col2:
                if st.button("Clear documents"):
                    # Remove all docs and vector DB, then reset state
                    if os.path.exists("docs"):
                        # Delete files inside docs folder
                        for name in os.listdir("docs"):
                            try:
                                os.remove(os.path.join("docs", name))
                            except Exception:
                                pass
                    # Remove persistent Chroma directory entirely
                    if os.path.exists("Vector_DB - Documents"):
                        try:
                            shutil.rmtree("Vector_DB - Documents")
                        except Exception:
                            pass
                    # Reset session state related to documents and vectordb
                    st.session_state.uploaded_pdfs = []
                    st.session_state.processed_documents = []
                    st.session_state.vectordb = None
                    st.session_state.previous_upload_docs_length = 0
                    st.success("All documents and vector database cleared.")

            # Delete specific documents
            if upload_docs:
                st.write("")
                to_delete = st.multiselect("Select documents to delete", options=upload_docs, default=[])
                if to_delete and st.button("Delete selected"):
                    # 1) Delete files from docs folder
                    for name in to_delete:
                        path = os.path.join("docs", name)
                        try:
                            if os.path.exists(path):
                                os.remove(path)
                        except Exception:
                            pass
                    # 2) Delete corresponding vectors from Chroma by metadata 'source'
                    if st.session_state.vectordb is not None:
                        try:
                            sources = [os.path.join("docs", name) for name in to_delete]
                            st.session_state.vectordb.delete(where={"source": {"$in": sources}})
                        except Exception:
                            # If delete by filter is unsupported in this version, ignore
                            pass
                    # 3) Refresh in-memory state and vectordb as needed
                    upload_docs = os.listdir("docs")
                    st.session_state.processed_documents = upload_docs
                    st.session_state.previous_upload_docs_length = len(upload_docs)
                    # If no docs remain, null out vectordb
                    if not upload_docs:
                        st.session_state.vectordb = None
                        # Remove Chroma folder if empty
                        if os.path.exists("Vector_DB - Documents"):
                            try:
                                shutil.rmtree("Vector_DB - Documents")
                            except Exception:
                                pass
                    st.success("Selected documents deleted.")

        # Unlocks the chat when document is uploaded
        if self.docs_files or st.session_state.uploaded_pdfs:
            # Check to see if a new document was uploaded to update the vectordb variable in the session state
            if len(upload_docs) > st.session_state.previous_upload_docs_length:
                st.session_state.vectordb = get_vectorstore(upload_docs, from_session_state=True)
                st.session_state.previous_upload_docs_length = len(upload_docs)
            # If we have docs on disk but no vector DB (e.g., DB was cleared), build it now
            if upload_docs and st.session_state.vectordb is None:
                st.session_state.vectordb = get_vectorstore(upload_docs, from_session_state=False)
            # Only enable chat if a vector DB is available
            if st.session_state.vectordb is not None:
                st.session_state.chat_history = chat(st.session_state.chat_history, st.session_state.vectordb)

        # Locks the chat until a document is uploaded
        if (not self.docs_files and not st.session_state.uploaded_pdfs) or st.session_state.vectordb is None:
            st.info("Upload a pdf file to chat with it. You can keep uploading files to chat with, and if you need to leave, you won't need to upload these files again")

if __name__ == "__main__":
    app = ChatApp()
    app.run()