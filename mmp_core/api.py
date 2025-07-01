import frappe
from frappe.utils import now_datetime, time_diff_in_seconds, datetime

@frappe.whitelist(allow_guest=True, methods=["GET"])
def ping():
    """
    Simple endpoint to check if the server is running.
    """
    return {"status": "ok", "message": "Server is running"}

@frappe.whitelist(allow_guest=True, methods=["POST"])
def log_and_set_workstation_status(**kwargs):
    """
    Hybrid Approach:
    1. Logs historical machine activity in the custom 'Machine Activity Log' DocType.
    2. Updates the built-in 'Status' field on the Workstation DocType.
    """

    data = frappe.local.form_dict
    device_id = data.get("device_id")
    new_status = data.get("status")

    if not device_id or not new_status:
        frappe.throw("Device ID and status are required fields.")
    
    # Find the ERPNext Workstation linked to the ThingsBoard device
    workstation_name = frappe.db.get_value("Workstation", 
        {"custom_thingsboard_device_id": device_id}, "name")
    
    if not workstation_name:
        frappe.log_error(f"No workstation found for device ID: {device_id}", "Machine Activity Log Error")
        return {"status": "error", "message": "Workstation not found"}
    
    workstation_doc = frappe.get_doc("Workstation", workstation_name)
    current_status_on_workstation = workstation_doc.status

    if new_status == current_status_on_workstation:
        return {"status": "ignored", "message": "Status unchanged"}
    else:
        now = datetime.datetime.utcnow()

        # Step 1: Find the most recent log entry and "close it out"
        last_log = frappe.get_all(
            "Machine Activity Log",
            filters={"workstation": workstation_name, "end_time": ("is", "not set")},
            fields=["name", "start_time"],
            limit=1
        )
        if last_log:
            last_log_doc = frappe.get_doc("Machine Activity Log", last_log[0].name)
            last_log_doc.end_time = now
            last_log_doc.duration_seconds = time_diff_in_seconds(now, last_log_doc.start_time)
            last_log_doc.save(ignore_permissions=True)

        # Step 2: Create the new log entry for the new status
        new_log = frappe.new_doc("Machine Activity Log")
        new_log.workstation = workstation_name
        new_log.status = new_status
        new_log.start_time = now
        new_log.workstation_and_status = f"{workstation_name}-{new_status}" # For autonaming
        new_log.insert(ignore_permissions=True)

        # Step 3: Update the workstation's current status field
        workstation_doc.status = new_status
        workstation_doc.save(ignore_permissions=True)

        frappe.db.commit() # Commit all changes to the database
        return {"status": "success", "message": f"Logged and set new status '{new_status}' for {workstation_name}"}



