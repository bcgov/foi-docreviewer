from reviewer_api.models.FOIPAARedlineContent import RedlineContent
import uuid

class redlinecontentservice:

    def save_redline_content(self, redline_content_list, createdby=None,ministryrequestid=None):
        """
        Save a list of redline content dicts to the database.
        Each dict should have: ministryrequestid, documentid, type, section, content, category
        """
        dict_items = []
        new_uuid = str(uuid.uuid4())
        first_redline_content_section = next(
            (item for item in redline_content_list if item.get('type') == 'RedlineContentSection'),
            None
        )
        for item in redline_content_list:
            if item.get('type') == 'RedlineContent':
                dict_items.append({
                    "redlineid": new_uuid,
                    "ministryrequestid": ministryrequestid,
                    "documentid": item.get('documentid'),
                    "type": item.get('type'),
                    "section": first_redline_content_section.get('text'),  # Use 'text' for section
                    "content": item.get('text'),  
                    "category": item.get('category'),
                    "createdby": createdby,
                    "annotationid": item.get('annotationid'),
                    "pagenumber": item.get('page'),
                    "createdat": None  # Let model/db default handle this if needed
                })                
        result = RedlineContent.save(dict_items)
        return result