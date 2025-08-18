// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Job Applicant Overview"] = {
    'filters': [
        {
            fieldname: "job_title",
            label: "Job Title",
            fieldtype: "Link",
            options: "Job Opening"
        },
        {
            fieldname: "company",
            label: "Company",
            fieldtype: "Link",
            options: "Company"
        },
        {
            fieldname: "applicant_name",
            label: "Applicant Name",
            fieldtype: "Data"
        },
        {
            fieldname: "status",
            label: "Applicant Status",
            fieldtype: "Select",
            options: ["", "Open", "Rejected", "Accepted", "On Hold"]
        },
        {
            fieldname: "assessment",
            label: "Assessment",
            fieldtype: "Select",
            default: "All",
            options: ["All", "Meet Requirements", "Partially Meet Requirements", "Not Meet Requirements"]
        }
    ],
    'onload': function (report) {
        hide_chart_buttons();

        report.page.add_inner_button(__('Reject'), function () {
            const assessment_filter = report.get_filter_value("assessment");
            const status = report.get_filter_value("status");
            if (!(assessment_filter === "Not Meet Requirements" || status === "Open")) {
                frappe.msgprint(__('Reject action only available when filter "Assessment" is set to "Not Meet Requirements" or filter "Applicant Status" is set to "Open".'));
                return;
            }

            const d = new frappe.ui.Dialog({
                title: __("Reject Applicants"),
                fields: [
                    {
                        label: 'Email Template',
                        fieldname: 'email_template',
                        fieldtype: 'Link',
                        options: 'Email Template',
                        reqd: 1,
                        change: function () {
                            const template_name = d.get_value('email_template');
                            if (template_name) {
                                frappe.call({
                                    'method': "frappe.client.get",
                                    'args': {
                                        'doctype': "Email Template",
                                        'name': template_name
                                    },
                                    'callback': function (r) {
                                        const content = r.message && r.message.response;
                                        if (content) {
                                            d.set_value('email_message', content);
                                        }
                                    }
                                });
                            }
                        }
                    },
                    {
                        label: 'Email Subject',
                        fieldname: 'email_subject',
                        fieldtype: 'Data',
                        default: 'Your Application',
                        reqd: 1
                    },
                    {
                        label: 'BCC (Optional)',
                        fieldname: 'bcc',
                        fieldtype: 'Data'
                    },
                    {
                        label: 'Email Message',
                        fieldname: 'email_message',
                        fieldtype: 'Text Editor',
                        reqd: 1
                    }
                ],
                primary_action_label: 'Send & Reject',
                primary_action(values) {
					const rows = report.data;

					// Prepare data to send
					const applicants = rows.map(row => ({
						'email_id': row.email_id,
						'job_applicant': row.job_applicant,
						'salutation': row.salutation || "",
						'applicant_name': row.applicant_name || ""
					}));

					frappe.call({
						'method': "microsynth.microsynth.report.job_applicant_overview.job_applicant_overview.send_rejection_emails",
						'args': {
							'template': values.email_message,
							'subject': values.email_subject,
							'bcc': values.bcc || "",
							'applicants': JSON.stringify(applicants)
						},
						'callback': function(r) {
							frappe.msgprint(r.message);
							d.hide();
						}
					});
				}
            });
            d.show();
        });
    }
};
