import functions_framework
from flask import Flask, jsonify, request
from firebase_admin import initialize_app, firestore

initialize_app()

app = Flask(__name__)

@functions_framework.http
def user_details_api(request):
    """
    API to retrieve user details from Firestore based on phone number.
    Accepts phone_no in the request body (POST).
    """
    if request.method == 'POST':
        try:
            request_json = request.get_json()

            if request_json and 'phone_no' in request_json:
                phone_no = request_json['phone_no']
            else:
                return jsonify({"error": "Missing phone_no in request body"}), 400

            db = firestore.client()
            users_ref = db.collection('eazybank-applications')

            # Query Firestore for the document where phone_no matches
            query = users_ref.where('phone_no', '==', phone_no).limit(1)

            results = query.get()

            if not results:
                return jsonify({"error": "User not found with phone_no: {}".format(phone_no)}), 404

            # Assuming phone_no is unique, there should be only one result
            for doc in results:
                user_data = doc.to_dict()

                user_details = {
                    'user_name': user_data.get('user_name'),
                    'account_status': user_data.get('account_status'),
                    'reason': user_data.get('reason'),
                    'account_number': user_data.get('account_number'),
                    'account_balance': user_data.get('account_balance'),
                    'credit_card_number': user_data.get('credit_card_number')
                }

                return jsonify(user_details), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Only POST requests are allowed"}), 405
