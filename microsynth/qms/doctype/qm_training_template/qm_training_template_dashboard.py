# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from frappe import _


def get_data():
	return {
		'fieldname': 'training_template',
		'transactions': [
			{
				'label': _('Trainings'),
				'items': ['QM Training Course'],
			},
		],
	}
