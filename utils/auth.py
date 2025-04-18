"""
    fatsecret
    ---------

    Simple python wrapper of the Fatsecret API

"""

import datetime

from rauth.service import OAuth1Service
from utils.exceptions import BaseFatsecretError, GeneralError, AuthenticationError, ParameterError, ApplicationError
from utils.constants import NAME, REQUEST_TOKEN_URL, ACCESS_TOKEN_URL, AUTHORIZE_URL, BASE_URL
# FIXME add method to set default units and make it an optional argument to the constructor
class Fatsecret:
    """
    Session for API interaction

    Can have an unauthorized session for access to public data or a 3-legged Oauth authenticated session
    for access to Fatsecret user profile data

    Fatsecret only supports OAuth 1.0 with HMAC-SHA1 signed requests.

    """

    def __init__(self, consumer_key, consumer_secret, session_token=None):
        """Create unauthorized session or open existing authorized session

        :param consumer_key: App API Key. Register at https://platform.fatsecret.com/api/
        :type consumer_key: str
        :param consumer_secret: Secret app API key
        :type consumer_secret: str
        :param session_token: Access Token / Access Secret pair from existing authorized session
        :type session_token: tuple
        """

        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

        # Needed for new access. Generated by running get_authorize_url()
        self.request_token = None
        self.request_token_secret = None

        # Required for accessing user info. Generated by running authenticate()
        self.access_token = None
        self.access_token_secret = None

        self.oauth = OAuth1Service(
            name=NAME,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            request_token_url=REQUEST_TOKEN_URL,
            access_token_url=ACCESS_TOKEN_URL,
            authorize_url=AUTHORIZE_URL,
            base_url=BASE_URL,
        )

        # Open prior session or default to unauthorized session
        if session_token:
            self.access_token = session_token[0]
            self.access_token_secret = session_token[1]
            self.session = self.oauth.get_session(token=session_token)
        else:
            # Default to unauthorized session
            self.session = self.oauth.get_session()

    @property
    def api_url(self):

        return BASE_URL

    def get_authorize_url(self, callback_url="oob"):
        """URL used to authenticate app to access Fatsecret User data

        If no callback url is provided then you'll need to allow the user to enter in a PIN that Fatsecret
        displays once access was allowed by the user

        :param callback_url: An absolute URL to redirect the User to when they have completed authentication
        :type callback_url: str
        """
        self.request_token, self.request_token_secret = self.oauth.get_request_token(
            method="GET", params={"oauth_callback": callback_url}
        )

        return self.oauth.get_authorize_url(self.request_token)

    def authenticate(self, verifier):
        """Retrieve access tokens once user has approved access to authenticate session

        :param verifier: PIN displayed to user or returned by authorize_url when callback url is provided
        :type verifier: int
        """

        session_token = self.oauth.get_access_token(
            self.request_token,
            self.request_token_secret,
            params={"oauth_verifier": verifier},
        )

        self.access_token = session_token[0]
        self.access_token_secret = session_token[1]
        self.session = self.oauth.get_session(session_token)

        # Return session token for app specific caching
        return session_token

    def close(self):
        """Session cleanup"""
        self.session.close()

    @staticmethod
    def unix_time(dt):
        """Convert the provided datetime into number of days since the Epoch

        :param dt: Date to convert
        :type dt: datetime.datetime
        """
        epoch = datetime.datetime.utcfromtimestamp(0)
        delta = dt - epoch
        return delta.days

    @staticmethod
    def valid_response(response):
        """Helper function to check JSON response for errors and to strip headers

        :param response: JSON response from API call
        :type response: requests.Response
        """
        if response.json():

            for key in response.json():

                # Error Code Handling
                if key == "error":
                    code = response.json()[key]["code"]
                    message = response.json()[key]["message"]
                    if code == 2:
                        raise AuthenticationError(
                            2, "This api call requires an authenticated session"
                        )

                    elif code in [1, 10, 11, 12, 20, 21]:
                        raise GeneralError(code, message)

                    elif 3 <= code <= 9:
                        raise AuthenticationError(code, message)

                    elif 101 <= code <= 108:
                        raise ParameterError(code, message)

                    elif 201 <= code <= 207:
                        raise ApplicationError(code, message)

                # All other response options
                elif key == "success":
                    return True

                elif key == "foods":
                    return response.json()[key]["food"]

                elif key == "suggestions":
                    return response.json()[key]

                elif key == "recipes":
                    return response.json()[key]["recipe"]

                elif key == "saved_meals":
                    return response.json()[key]["saved_meal"]

                elif key == "saved_meal_items":
                    return response.json()[key]["saved_meal_item"]

                elif key == "exercise_types":
                    return response.json()[key]["exercise"]

                elif key == "food_entries":
                    if response.json()[key] is None:
                        return []
                    entries = response.json()[key]["food_entry"]
                    if type(entries) == dict:
                        return [entries]
                    elif type(entries) == list:
                        return entries

                elif key == "month":
                    return response.json()[key]["day"]

                elif key == "profile":
                    if "auth_token" in response.json()[key]:
                        return (
                            response.json()[key]["auth_token"],
                            response.json()[key]["auth_secret"],
                        )
                    else:
                        return response.json()[key]

                elif key in (
                    "food",
                    "recipe",
                    "recipe_types",
                    "saved_meal_id",
                    "saved_meal_item_id",
                    "food_entry_id",
                ):
                    return response.json()[key]

    def food_get(self, food_id):
        """Returns detailed nutritional information for the specified food.

        Use this call to display nutrition values for a food to users.

        :param food_id: Fatsecret food identifier
        :type food_id: str
        """

        params = {"method": "food.get", "food_id": food_id, "format": "json"}

        response = self.session.get(self.api_url, params=params)
        return self.valid_response(response)

    def food_get_v2(self, food_id, region=None, language=None):
        """Returns detailed nutritional information for the specified food.

        Use this call to display nutrition values for a food to users.

        :param food_id: Fatsecret food identifier
        :type food_id: str
        """

        params = {"method": "food.get.v2", "food_id": food_id, "format": "json"}

        if region:
            params["region"] = region

        if language:
            params["language"] = language

        response = self.session.get(self.api_url, params=params)
        return self.valid_response(response)

    def foods_get_favorites(self):
        """Returns the favorite foods for the authenticated user."""

        params = {"method": "foods.get_favorites", "format": "json"}

        response = self.session.get(self.api_url, params=params)
        return self.valid_response(response)

    def foods_get_most_eaten(self, meal=None):
        """Returns the most eaten foods for the user according to the meal specified.

        :param meal: 'breakfast', 'lunch', 'dinner', or 'other'
        :type meal: str
        """
        params = {"method": "foods.get_most_eaten", "format": "json"}

        if meal in ["breakfast", "lunch", "dinner", "other"]:
            params["meal"] = meal

        response = self.session.get(self.api_url, params=params)
        return self.valid_response(response)

    def foods_get_recently_eaten(self, meal=None):
        """Returns the recently eaten foods for the user according to the meal specified

        :param meal: 'breakfast', 'lunch', 'dinner', or 'other'
        :type meal: str
        """
        params = {"method": "foods.get_recently_eaten", "format": "json"}

        if meal in ["breakfast", "lunch", "dinner", "other"]:
            params["meal"] = meal

        response = self.session.get(self.api_url, params=params)
        return self.valid_response(response)

    def saved_meal_create(self, meal_name, meal_desc=None, meals=None):
        """Records a saved meal for the user according to the parameters specified.

        :param meal_name: The name of the saved meal.
        :type meal_name: str
        :param meal_desc: A short description of the saved meal.
        :type meal_desc: str
        :param meals: A comma separated list of the types of meal this saved meal is suitable for.
            Valid meal types are "breakfast", "lunch", "dinner" and "other".
        :type meals: list
        """

        params = {
            "method": "saved_meal.create",
            "format": "json",
            "saved_meal_name": meal_name,
        }
        if meal_desc:
            params["saved_meal_description"] = meal_desc
        if meals:
            params["meals"] = ",".join(meals)

        response = self.session.get(self.api_url, params=params)
        return self.valid_response(response)

    def saved_meal_get(self, meal=None):
        """Returns saved meals for the authenticated user

        :param meal: Filter result set to 'Breakfast', 'Lunch', 'Dinner', or 'Other'
        :type meal: str
        """

        params = {"method": "saved_meals.get", "format": "json"}

        if meal:
            params["meal"] = meal

        response = self.session.get(self.api_url, params)
        return self.valid_response(response)

    def saved_meal_item_add(
        self, meal_id, food_id, food_entry_name, serving_id, num_units
    ):
        """Adds a food to a user's saved meal according to the parameters specified.

        :param meal_id: The ID of the saved meal.
        :type meal_id: str
        :param food_id: The ID of the food to add to the saved meal.
        :type food_id: str
        :param food_entry_name: The name of the food to add to the saved meal.
        :type food_entry_name: str
        :param serving_id: The ID of the serving of the food to add to the saved meal.
        :type serving_id: str
        :param num_units: The number of servings of the food to add to the saved meal.
        :type num_units: float
        """
        params = {
            "method": "saved_meal_item.add",
            "format": "json",
            "saved_meal_id": meal_id,
            "food_id": food_id,
            "food_entry_name": food_entry_name,
            "serving_id": serving_id,
            "number_of_units": num_units,
        }

        response = self.session.get(self.api_url, params)
        return self.valid_response(response)

    def saved_meal_items_get(self, meal_id):
        """Returns saved meal items for a specified saved meal.

        :param meal_id: The ID of the saved meal to retrieve the saved_meal_items for.
        :type meal_id: str
        """

        params = {
            "method": "saved_meal_items.get",
            "format": "json",
            "saved_meal_id": meal_id,
        }

        response = self.session.get(self.api_url, params=params)
        return self.valid_response(response)


    # def profile_create(self, user_id=None):
    #     """Creates a new profile and returns the oauth_token and oauth_secret for the new profile.

    #     The token and secret returned by this method are persisted indefinitely and may be used in order to
    #     provide profile-specific information storage for users including food and exercise diaries and weight tracking.

    #     :param user_id: You can set your own ID for the newly created profile if you do not wish to store the
    #         auth_token and auth_secret. Particularly useful if you are only using the FatSecret JavaScript API.
    #         Use profile.get_auth to retrieve auth_token and auth_secret.
    #     :type user_id: str
    #     """

    #     params = {"method": "profile.create", "format": "json"}

    #     if user_id:
    #         params["user_id"] = user_id

    #     response = self.session.get(self.api_url, params=params)

    #     return self.valid_response(response)

    def profile_get(self):
        """Returns general status information for a nominated user."""

        params = {"method": "profile.get", "format": "json"}
        response = self.session.get(self.api_url, params=params)

        return self.valid_response(response)

    def profile_get_auth(self, user_id):
        """Returns the authentication information for a nominated user.

        :param user_id: The user_id specified in profile.create.
        :type user_id: str
        """

        params = {"method": "profile.get_auth", "format": "json", "user_id": user_id}

        response = self.session.get(self.api_url, params=params)
        return self.valid_response(response)


    def food_entries_get(self, food_entry_id=None, date=None):
        """Returns saved food diary entries for the user according to the filter specified.

        This method can be used to return all food diary entries recorded on a nominated date or a single food
        diary entry with a nominated food_entry_id.

        :: You must specify either date or food_entry_id.

        :param food_entry_id: The ID of the food entry to retrieve. You must specify either date or food_entry_id.
        :type food_entry_id: str
        :param date: Day to filter food entries by (default value is the current day).
        :type date: datetime.datetmie
        """

        params = {"method": "food_entries.get", "format": "json"}

        if food_entry_id:
            params["food_entry_id"] = food_entry_id
        elif date:
            params["date"] = self.unix_time(date)
        else:
            return  # exit without running as no valid parameter was provided

        response = self.session.get(self.api_url, params=params)
        return self.valid_response(response)

    def food_entries_get_month(self, date=None):
        """Returns summary daily nutritional information for a user's food diary entries for the month specified.

        Use this call to display nutritional information to users about their food intake for a nominated month.

        :param date: Day in the month to return (default value is the current day to get current month).
        :type date: datetime.datetime
        """

        params = {"method": "food_entries.get_month", "format": "json"}

        if date:
            params["date"] = self.unix_time(date)

        response = self.session.get(self.api_url, params=params)
        return self.valid_response(response)
