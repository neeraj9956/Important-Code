# Permission Query Code


import frappe
@frappe.whitelist()
def user_doc_permission_for_parent(user):
    if not user:
        user = frappe.session.user
    roles = frappe.get_roles(user)
    if user != "Administrator" and ('Parent' in roles):
        student_data = frappe.get_all("Student", {"custom_student_parent": frappe.session.user},["name","user"])
        if len(student_data)>0:
            student_names = [student.get("user") for student in student_data]
            student_names.append(frappe.session.user)
        return """(`tabUser`.name in {0})""".format(tuple(student_names))
    elif user != "Administrator" and ('Student' in roles):
        return """(`tabUser`.name = '{0}')""".format(frappe.session.user)
    elif user != "Administrator" and ('Employee' in roles):
        return """(`tabUser`.name = '{0}')""".format(frappe.session.user)
   
@frappe.whitelist()     
def program_doc_permission(user):
    if not user:
        user = frappe.session.user
    roles = frappe.get_roles(user)     
    
    if user != "Administrator" and ('Parent' in roles):
        program_data = frappe.get_all("Student", {"custom_student_parent": frappe.session.user}, ["name", "user", "custom_course"])
        if len(program_data) > 0:
            program_name = [program.get("custom_course") for program in program_data]
        return """(`tabProgram`.name in {0})""".format(tuple(program_name))
    elif user != "Administrator" and ('Student' in roles):
        student_program_data = frappe.get_all("Student", {"user": frappe.session.user}, ["name", "user", "custom_course"])
        if student_program_data:
            student_program_name= [course.get("custom_course") for course in student_program_data]
        return """(`tabProgram`.name = '{0}')""".format(student_program_name[0]) 

@frappe.whitelist()
def wiki_doc_permission(user):
    if not user:
        user = frappe.session.user
    roles = frappe.get_roles(user)
    wiki = []
    if user != "Administrator" and ('Student' in roles):
        wiki_page = frappe.get_all("Student", {"user": frappe.session.user}, ["name", "user", "custom_student_policy", "custom_school_policy"])
        if wiki_page:
            wiki_student_policy =[wiki.get("custom_student_policy") for wiki in wiki_page]
            wiki_school_policy=[wiki.get("custom_school_policy") for wiki in wiki_page]
            wiki.extend(wiki_student_policy)
            wiki.extend(wiki_school_policy)
        return """(`tabWiki Page`.name in {0})""".format(tuple(wiki))
    elif if user != "Administrator" and ('Parent' in roles):
        wiki_page = frappe.get_all("Student", {"custom_student_parent": frappe.session.user}, ["name", "user", "custom_student_policy", "custom_school_policy"])
        if wiki_page:
            wiki_student_policy =[wiki.get("custom_student_policy") for wiki in wiki_page]
            wiki_school_policy=[wiki.get("custom_school_policy") for wiki in wiki_page]
            wiki.extend(wiki_student_policy)
            wiki.extend(wiki_school_policy)
        return """(`tabWiki Page`.name in {0})""".format(tuple(wiki))

    elif user !="Administrator" and ('Employee' in roles):
        emp_wiki_page=frappe.get_all('Employee',{"user_id":frappe.session.user},["name","user_id","custom_student_policy","custom_employee_policy"])
        if emp_wiki_page:
            wiki_stu_policy=[wiki.get("custom_student_policy") for wiki in emp_wiki_page]
            wiki_emp_policy=[wiki.get("custom_employee_policy") for wiki in emp_wiki_page]
            wiki.extend(wiki_stu_policy)
            wiki.extend(wiki_emp_policy)
        return """(`tabWiki Page`.name in {0})""".format(tuple(wiki))

@frappe.whitelist()
def topic_doc_permission(user):
    if not user:
            user=frappe.session.user
    roles=frappe.get_roles(user)
    print("Current Roles -------------->",roles)
    if user!="Adminstrator" and ('Student' in roles):
        topic_list=frappe.get_all("Reference Topic",{"parenttype":roles},["name","topic_list"])
        if topic_list:
            topic_data=[topics.get("topic_list") for topics in topic_list]
            print("Topic List")
    return """(`tabTopic`.name in {0})""".format(tuple(topic_data))
import frappe

@frappe.whitelist()
def topic_doc_permission(user):
    if not user:
        user = frappe.session.user
    roles = frappe.get_roles(user)
    print("Current Roles -------------->", roles)
    topic_data = []  # Initialize topic_data outside the if block
    if user != "Administrator" and ('Student' in roles):
        topic_data = frappe.get_all("Reference Topic", filters={"parent": user}, fields=["name", "topic_list"])
        if topic_list:
            topic_data = [topics.get("topic_list") for topics in topic_list]
            print("Topic List")
    return """(`tabTopic`.name in {0})""".format(tuple(topic_data))


