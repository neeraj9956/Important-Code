frappe.provide("erpnext");
erpnext.utils.CRMActivities = class extends erpnext.utils.CRMActivities  {
        constructor(opts) {
            super(opts)
            $.extend(this, opts);
        }
    
	refresh() {
		var me = this;
		$(this.open_activities_wrapper).empty();
		let cur_form_footer = this.form_wrapper.find(".form-footer");

		// all activities
		if (!$(this.all_activities_wrapper).find(".form-footer").length) {
			this.all_activities_wrapper.empty();
			$(cur_form_footer).appendTo(this.all_activities_wrapper);

			// remove frappe-control class to avoid absolute position for action-btn
			$(this.all_activities_wrapper).removeClass("frappe-control");
			// hide new event button
			$(".timeline-actions").find(".btn-default").hide();
			// hide new comment box
			$(".comment-box").hide();
			// show only communications by default
			$($(".timeline-content").find(".nav-link")[0]).tab("show");
		}

		// open activities
		frappe.call({
			method: "erpnext.crm.utils.get_open_activities",
			args: {
				ref_doctype: this.frm.doc.doctype,
				ref_docname: this.frm.doc.name,
			},
			callback: (r) => {
				if (!r.exc) {
					if (r.message.tasks) {
						var tasksHtml = ActivityGenerator.generateTasksHtml(r.message.tasks);
						$(tasksHtml).appendTo(cur_frm.fields_dict.open_activities_html.wrapper);
					}
					if (r.message.events) {
						var eventsHtml = ActivityGenerator.generateEventsHtml(r.message.events);
						$(eventsHtml).appendTo(cur_frm.fields_dict.open_activities_html.wrapper);
					}
					me.create_task();
					me.create_event();
				}
			},
		});
	}

	create_task() {
		const me = this;
		const _create_task = () => {
			const args = {
				doc: me.frm.doc,
				frm: me.frm,
				title: __("New Task"),
			};
			const composer = new frappe.views.InteractionComposer(args);
			composer.dialog.get_field("interaction_type").set_value("ToDo");
			// hide column having interaction type field
			$(composer.dialog.get_field("interaction_type").wrapper).closest(".form-column").hide();
			// hide summary field
			$(composer.dialog.get_field("summary").wrapper).closest(".form-section").hide();
		};
		
		$(".new-task-btn").click(_create_task);
}

	create_event() {
		let me = this;
		let _create_event = async () => {
			try {
				let reference_doctype = me.frm.doctype;
				let reference_docname = me.frm.doc.name;
				let new_event = frappe.model.get_new_doc('Event');

				let new_participant = frappe.model.add_child(new_event, 'Event Participants', 'event_participants'); // Ensure correct child table DocType and fieldname
				new_participant.reference_doctype = reference_doctype;
				new_participant.reference_docname = reference_docname;

				frappe.set_route('Form', 'Event', new_event.name);
			} catch (error) {
				frappe.msgprint(__('Failed to create event: ' + error.message));
			}
		};
		$(".new-event-btn").click(_create_event);
	}
	async update_status(input_field, doctype) {
		let completed = $(input_field).prop("checked") ? 1 : 0;
		let docname = $(input_field).attr("name");
		if (completed) {
			await frappe.db.set_value(doctype, docname, "status", "Closed");
			this.refresh();
		}
	}
};


class ActivityGenerator {
    static generateTasksHtml(tasks) {
        var html = `
            <div class="open-activities">
                <div class="new-btn pb-3">
                    <span>
                        <button class="btn btn-sm small new-task-btn mr-1" style="font-weight:bold;border: 2px solid lightgrey;">
                            <svg class="icon icon-sm">
                                <use href="#icon-small-message"></use>
                            </svg>
                            New Task
                        </button>
                    </span>
                </div>`;
        if (tasks.length > 0) {
            tasks.forEach(task => {
                html += `<div class="single-activity card mb-2">`;
                html += `
                    <div class="flex justify-between mb-2">
                        <div class="label-area font-md ml-1">
                            <span class="mr-2">
                                <svg class="icon icon-sm">
                                    <use href="#icon-small-message"></use>
                                </svg>
                            </span>
                            <a href="/app/todo/${task.name}" title="Open Task" class="task-description">${task.description}</a>
                        </div>
                    </div>`;
                if (task.date) {
                    html += `<div class="text-muted ml-1">${frappe.datetime.global_date_format(task.date)}</div>`;
                }
                if (task.allocated_to) {
                    html += `<div class="text-muted ml-1">Allocated To: ${task.allocated_to}</div>`;
                }
                html += `</div>`;
            });
        } else {
            html += `<div class="single-activity no-activity text-muted">No open task</div>`;
        }
        html += `</div>`;
        return html;
    }

    static generateEventsHtml(events) {
        var html = `
            <div class="open-activities">
                <div class="new-btn pb-3">
                    <span>
                        <button class="btn btn-sm small new-event-btn mr-1" style="font-weight:bold;border: 2px solid lightgrey;">
                            <svg class="icon icon-sm">
                                <use href="#icon-calendar"></use>
                            </svg>
                            New Event
                        </button>
                    </span>
                </div>`;
        if (events.length > 0) {
            events.forEach(event => {
                html += `<div class="single-activity card mb-2">`;
                html += `
                    <div class="flex justify-between mb-2">
                        <div class="label-area font-md ml-1">
                            <span class="mr-2">
                                <svg class="icon icon-sm">
                                    <use href="#icon-small-message"></use>
                                </svg>
                            </span>
                            <a href="/app/event/${event.name}" title="Open Event" class="event-subject">${event.subject}</a>
                        </div>
                    </div>`;
                if (event.starts_on) {
                    html += `<div class="text-muted ml-1">${frappe.datetime.global_date_format(event.starts_on)}</div>`;
                }
                html += `</div>`;
            });
        } else {
            html += `<div class="single-activity no-activity text-muted">No open event</div>`;
        }
        html += `</div>`;
        return html;
    }
}

const style = document.createElement('style');
style.textContent = `
.open-activities {
    min-height: 50px;
    padding-left: 0px;
    padding-bottom: 15px !important;
}

.open-activities .new-btn {
    text-align: right;
}

.single-activity {
    min-height: 90px;
    border: 1px solid var(--border-color);
    padding: 10px;
    border-bottom: 0;
    padding-right: 10px; /* Adjust padding to ensure content stays within card */
    background: #fff;
    margin-bottom: 10px;
    box-sizing: border-box; /* Ensure padding and border are included in element's total width and height */
}

.single-activity.card {
    border-radius: 5px;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.single-activity:last-child {
    border-bottom: 1px solid var(--border-color);
}

.single-activity:hover .completion-checkbox {
    display: block;
}

.completion-checkbox {
    vertical-align: middle;
    display: none;
}

.open-tasks {
    width: 50%;
}

.open-tasks:first-child {
    border-right: 0;
}

.open-section-head {
    background-color: var(--bg-color);
    min-height: 30px;
    border-bottom: 1px solid var(--border-color);
    padding: 10px;
    font-weight: bold;
}

.no-activity {
    text-align: center;
    padding-top: 30px;
}

.form-footer {
    background-color: var(--bg-color);
}

.task-description, .event-subject {
    display: inline-block;
    max-width: 100%; 
    overflow: hidden;
    text-overflow: ellipsis;
    vertical-align: bottom;
}

.label-area {
    width: calc(100% - 20px);
    box-sizing: border-box; 
}
`;
document.head.appendChild(style);





erpnext.utils.CRMNotes = class CRMNotes {
	constructor(opts) {
		$.extend(this, opts);
	}

	refresh() {
		var me = this;
		this.notes_wrapper.find(".notes-section").remove();

		let notes = this.frm.doc.notes || [];
		notes.sort(function (a, b) {
			return new Date(b.added_on) - new Date(a.added_on);
		});

		let notes_html = frappe.render_template("crm_notes", {
			notes: notes,
		});
		$(notes_html).appendTo(this.notes_wrapper);

		this.add_note();

		$(".notes-section")
			.find(".edit-note-btn")
			.on("click", function () {
				me.edit_note(this);
			});

		$(".notes-section")
			.find(".delete-note-btn")
			.on("click", function () {
				me.delete_note(this);
			});
	}

	add_note() {
		let me = this;
		let _add_note = () => {
			var d = new frappe.ui.Dialog({
				title: __("Add a Note"),
				fields: [
					{
						label: "Note",
						fieldname: "note",
						fieldtype: "Text Editor",
						reqd: 1,
						enable_mentions: true,
					},
				],
				primary_action: function () {
					var data = d.get_values();
					frappe.call({
						method: "add_note",
						doc: me.frm.doc,
						args: {
							note: data.note,
						},
						freeze: true,
						callback: function (r) {
							if (!r.exc) {
								me.frm.refresh_field("notes");
								me.refresh();
							}
							d.hide();
						},
					});
				},
				primary_action_label: __("Add"),
			});
			d.show();
		};
		$(".new-note-btn").click(_add_note);
	}

	edit_note(edit_btn) {
		var me = this;
		let row = $(edit_btn).closest(".comment-content");
		let row_id = row.attr("name");
		let row_content = $(row).find(".content").html();
		if (row_content) {
			var d = new frappe.ui.Dialog({
				title: __("Edit Note"),
				fields: [
					{
						label: "Note",
						fieldname: "note",
						fieldtype: "Text Editor",
						default: row_content,
					},
				],
				primary_action: function () {
					var data = d.get_values();
					frappe.call({
						method: "edit_note",
						doc: me.frm.doc,
						args: {
							note: data.note,
							row_id: row_id,
						},
						freeze: true,
						callback: function (r) {
							if (!r.exc) {
								me.frm.refresh_field("notes");
								me.refresh();
								d.hide();
							}
						},
					});
				},
				primary_action_label: __("Done"),
			});
			d.show();
		}
	}

	delete_note(delete_btn) {
		var me = this;
		let row_id = $(delete_btn).closest(".comment-content").attr("name");
		frappe.call({
			method: "delete_note",
			doc: me.frm.doc,
			args: {
				row_id: row_id,
			},
			freeze: true,
			callback: function (r) {
				if (!r.exc) {
					me.frm.refresh_field("notes");
					me.refresh();
				}
			},
		});
	}
};
