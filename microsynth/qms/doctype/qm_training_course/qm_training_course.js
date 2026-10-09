// Copyright (c) 2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Training Course', {
	refresh: function(frm) {
		if (can_propose_participants(frm)) {
			frm.add_custom_button(__('Propose Participants'), function() {
				propose_participants(frm);
			});
		}
	}
});


function can_propose_participants(frm) {
	const permission = frm.perm && frm.perm[0];
	return frm.doc.docstatus === 0 && frm.doc.training_template && permission
		&& (frm.is_new() ? permission.create : permission.write);
}


function propose_participants(frm) {
	if (!can_propose_participants(frm)) {
		return;
	}
	const training_template = frm.doc.training_template;
	const course_name = frm.doc.name;
	function is_current_course() {
		return frm.doc.name === course_name && frm.doc.training_template === training_template
			&& can_propose_participants(frm);
	}
	frappe.call({
		method: 'microsynth.qms.doctype.qm_training_course.qm_training_course.get_proposed_participants',
		args: {
			training_template: training_template,
			docname: frm.is_new() ? null : course_name
		},
		callback: function(response) {
			if (!is_current_course()) {
				return;
			}
			const assigned = new Set((frm.doc.participants || []).map(row => row.user));
			const participants = (response.message || []).filter(row => !assigned.has(row.user));
			if (!participants.length) {
				frappe.msgprint(__('No additional participants with outstanding competencies are available for this Training Template.'));
				return;
			}
			const dialog = new frappe.ui.Dialog({
				title: __('Propose Participants'),
				size: 'large',
				fields: [{ fieldname: 'participant_selection', fieldtype: 'HTML' }],
				primary_action_label: __('Add'),
				primary_action: function() {
					if (!is_current_course()) {
						frappe.msgprint(__('The QM Training Course has changed. Please reopen the participant selection.'));
						dialog.hide();
						return;
					}
					const existing = new Set((frm.doc.participants || []).map(row => row.user));
					let added = false;
					$list.find('input:checked').each(function() {
						const participant = participants[Number($(this).val())];
						if (existing.has(participant.user)) {
							return;
						}
						frm.add_child('participants', { user: participant.user });
						existing.add(participant.user);
						added = true;
					});
					if (added) {
						frm.dirty();
						frm.refresh_field('participants');
					}
					dialog.hide();
				}
			});
			const $wrapper = dialog.fields_dict.participant_selection.$wrapper;
			const $actions = $('<div class="clearfix" style="margin-bottom: 12px;"></div>').appendTo($wrapper);
			const $list = $('<div style="max-height: 55vh; overflow-y: auto;"></div>').appendTo($wrapper);
			$('<button type="button" class="btn btn-default btn-sm"></button>')
				.text(__('Select all')).appendTo($actions)
				.on('click', () => $list.find('input').prop('checked', true));
			$('<button type="button" class="btn btn-default btn-sm" style="margin-left: 8px;"></button>')
				.text(__('Deselect all')).appendTo($actions)
				.on('click', () => $list.find('input').prop('checked', false));

			participants.forEach((participant, index) => {
				const $label = $('<label style="display: flex; align-items: baseline; gap: 8px; padding: 8px; border-bottom: 1px solid #eee; font-weight: normal; cursor: pointer;"></label>')
					.appendTo($list);
				$('<input type="checkbox">').val(index).appendTo($label);
				const $text = $('<span></span>').appendTo($label);
				$('<strong></strong>').text(participant.employee_name || participant.employee).appendTo($text);
				$('<small class="text-muted" style="display: block;"></small>')
					.text(participant.employee + ' · ' + participant.user).appendTo($text);
			});
			dialog.show();
		}
	});
}
