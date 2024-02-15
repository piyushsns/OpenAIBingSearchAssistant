from time import sleep
from openai import OpenAI
from dotenv import load_dotenv
import os, requests, time, json
from urllib.parse import quote
from msrest.authentication import CognitiveServicesCredentials
from azure.cognitiveservices.search.websearch import WebSearchClient
from azure.cognitiveservices.search.websearch.models import SafeSearch

class OpenAIBingSearchAssistant(OpenAI):
  def __init__(self):
    self.openai_api_key = os.environ["OPENAI_API_KEY"]
    self.bing_api_key = os.environ["AZURE_SUBSCRIPTION_KEY"]
    self.custom_config_id = os.environ["CUSTOM_CONFIGURATION_ID"]
    self.base_model = os.environ["OPENAI_MODEL"]
    self.assistant = None
    self.mainThread = None
    self.message = None
    self.runThread = None
    self.s_results = None
    self.u_request = None
    self.openai_client = self.initialize_openai()

  def initialize_openai(self):
      return OpenAI(api_key=self.openai_api_key)

  def create_assistant(self, assistantName, assistantInstructions, assistantToolsArray):
    self.assistant = self.openai_client.beta.assistants.create(
      name=assistantName,
      instructions=assistantInstructions,
      model=self.base_model,
      tools=assistantToolsArray
    )
    print(f"Assistant Created Succesfully: {self.assistant.id}\n")
    return self.assistant

  def retrieve_assistant(self, assistantId):
    self.assistant = self.openai_client.beta.assistants.retrieve(assistant_id=assistantId)
    print(f"Assistant Retrieved Succesfully: {self.assistant.id}\n")
    return self.assistant

  def create_main_thread(self):
    self.mainThread = self.openai_client.beta.threads.create()
    print(f"Main Thread Created Succesfully: {self.mainThread.id}\n")
    return self.mainThread

  def retrieve_main_thread(self, mainThreadId):
    self.mainThread = self.openai_client.beta.threads.retrieve(mainThreadId)
    print(f"Main Thread Retrieved Succesfully: {self.mainThread.id}\n")
    return self.mainThread

  def create_message_thread(self, **kwargs):
    self.message = self.openai_client.beta.threads.messages.create(thread_id=self.mainThread.id,**kwargs)
    print(f"Thread Message Created Succesfully: {self.message.id}\n")
    sleep(0.5)
    return self.message

  def retrieve_message_thread(self, message_id):
    self.message = self.openai_client.beta.threads.messages.retrieve(message_id)
    print(f"Thread Message Retrieved Succesfully: {self.message.id}\n")
    return self.message

  def create_thread_run(self):
    self.runThread = self.openai_client.beta.threads.runs.create(thread_id=self.mainThread.id, assistant_id=self.assistant.id)
    print(f"Thread Run Created Succesfully: {self.runThread.id}\n")
    sleep(0.5)
    return self.runThread

  def retrieve_thread_run(self, run_id):
    self.runThread = self.openai_client.beta.threads.runs.retrieve(run_id=run_id, thread_id=self.mainThread.id)
    print(f"Thread Run Retrieved Succesfully: {self.runThread.id}\n")
    return self.runThread

  def fetch_current_runing_thread(self):
    return self.openai_client.beta.threads.runs.retrieve(thread_id=self.mainThread.id, run_id=self.runThread.id)

  # Function to perform bing search
  def perform_bing_search(self, user_request):
    """
    Perform a Bing search based on the user's request.

    Args:
        user_request (str): The user's request.

    Returns:
        str: A string containing the search results.
    """
    try:
        self.u_request = user_request
        print(f"\nGenerating a search_query for Bing based on this user request: {self.u_request}")

        # Construct the prompt for OpenAI
        openai_prompt = "Generate a search-engine query to satisfy this user's request: " + self.u_request

        # Request search query generation from OpenAI
        response = self.openai_client.chat.completions.create(
            model=self.base_model,
            messages=[{"role": "user", "content": openai_prompt}],
        )

        bing_query = response.choices[0].message.content.strip()

        print(f"\nBing search query: {bing_query}. Now executing the search...\n")

        # Execute the Bing search
        self.s_results = self.run_bing_search(bing_query.replace('"',''))
        return self.s_results

    except Exception as error:
        # Handle any exceptions that occur during the search operation
        print(f"Encountered exception in perform Bing search:: {error}")
        return ""

  # Function to run bing search
  def run_bing_search(self, search_query):
      """
      Perform a Bing search with the given query.

      Args:
          search_query (str): The search query to be performed.

      Returns:
          str: A string containing the search results.
      """
      try:
          results_text = ""

          # Define the base URL for the Bing custom search API
          base_url = "https://api.bing.microsoft.com/v7.0/custom/search?"

          # Construct the complete search query URL
          # bing_search_query = base_url + 'q=' + encoded_query # + '&' + 'customconfig=' + custom_config_id --> uncomment this if you are using 'Bing Custom Search'
          bing_search_query = base_url + 'q=' + quote(search_query)  + '&' + 'customconfig=' + self.custom_config_id + "&mkt=en-US"

          print("bing_search_query===>" + str(bing_search_query))

          # Send a GET request to the Bing search API
          bing_response = requests.get(bing_search_query, headers={'Ocp-Apim-Subscription-Key': self.bing_api_key})

          # Handle different response status codes
          if bing_response.status_code == 401:
              print(f"Bing Failed {bing_response.status_code} ==> {bing_response.text}")
          elif bing_response.status_code == 200:
              print("\n")
              # Parse the JSON response data
              response_data = json.loads(bing_response.text)
              # Extract search results from the response
              for result in response_data.get("webPages", {}).get("value", []):
                  results_text += result["name"] + "\n"
                  results_text += result["url"] + "\n"
                  results_text += result["snippet"] + "\n\n"
                  # Print individual search result details
                  print(f"Title: {result['name']}")
                  print(f"URL: {result['url']}")
                  print(f"Snippet: {result['snippet']}\n")
              print(f"Bing Search {bing_response.status_code} successfull crawled")
          else:
              print(f"Bing Search {bing_response.status_code} ==> {bing_response.text}")
      except Exception as error:
          # Handle any exceptions that occur during the search operation
          print(f"Encountered exception in run bing search:: {error}")
      # Return the aggregated search results
      return results_text

  # Function to wait for a run to complete
  def wait_for_run_completion(self):
      while True:
          time.sleep(1)
          run = self.fetch_current_runing_thread()
          print(f"Current run status: {run.status}")
          if run.status in ['completed', 'failed', 'requires_action']:
            return run

  # Function to handle tool output submission
  def submit_tool_outputs(self, run, tool_output_array=None, func_override=None):
    """
    Submit tool outputs for a given run.

    Args:
        run (Run): The run object.
        tool_output_array (list, optional): An array of tool outputs. Defaults to None.
        func_override (str, optional): The name of the function to override. Defaults to None.

    Returns:
        Run: The updated run object.
    """
    try:
        tools_to_call = run.required_action.submit_tool_outputs.tool_calls
        print(f"\nSubmitting tool outputs for thread_id: {self.mainThread.id}, run_id: {run.id}, tools_to_call: {tools_to_call}\n")

        if tool_output_array is None:
            tool_output_array = []

        for tool in tools_to_call:
            output = None
            outputJson = {}
            tool_call_id = tool.id
            function_name = func_override if func_override else tool.function.name
            function_args = tool.function.arguments

            if function_name == "perform_bing_search":
                print("[function call] perform_bing_search...\n")
                output = self.perform_bing_search(user_request=json.loads(function_args)["user_request"])
            elif function_name == "process_search_results":
                print("\n[function call] process_search_results...\n")
                output = self.process_search_results(json.loads(function_args)["search_results"])
            if output:
                print("\n[function result] Appending tool output array...\n\n")
                tool_output_array.append({"tool_call_id": tool_call_id, "output": output})

        if len(tool_output_array) > 0:
            return self.openai_client.beta.threads.runs.submit_tool_outputs(thread_id=self.mainThread.id, run_id=run.id, tool_outputs=tool_output_array)
        else:
            return None

    except Exception as error:
        # Handle any exceptions that occur during the tool output submission
        print(f"Encountered exception in submit tool outputs:: {error}")
        return None

  # Function to process search results
  def process_search_results(self, search_results):
      """
      Process the Bing search results using GPT.

      Args:
          search_results (str): The search results obtained from Bing.

      Returns:
          str: The analysis of the Bing search results.
      """
      try:
          print("Analyzing/processing Bing search results:-\n")
          # Use GPT to analyze the Bing search results
          prompt = f"Analyze these Bing search results: '{search_results}'\nbased on this user request: {self.u_request}"
          response = self.openai_client.chat.completions.create(model=self.base_model, messages=[{"role": "user", "content": prompt}])
          analysis = response.choices[0].message.content.strip()
          print(f"Analysis: {analysis}")
          return analysis
      except Exception as error:
          # Handle any exceptions that occur during the analysis
          print(f"Encountered exception in process search results:: {error}")
          return ""

  # Function to print messages from a thread
  def print_messages_from_thread(self):
    """
    Print messages from a thread with the specified thread ID.

    Args:
        thread_id (str): The ID of the thread.

    Returns:
        str: A string containing assistant messages.
    """
    try:
        messages = self.openai_client.beta.threads.messages.list(thread_id=self.mainThread.id)
        assistant_messages = ""
        print("\n\n====== Assistant Response ======\n")
        for msg in messages:
            if msg.role == "assistant":
                assistant_response = msg.content[0].text.value
                print(f"{msg.role}: {assistant_response}")
                assistant_messages += f"{msg.role}: {assistant_response}\n"
        return assistant_messages
    except Exception as error:
        print(f"\nEncountered exception in print messages from thread:: {error}")
        return ""

  # Function to ask to user promt
  def ask_to_user_promt(self):
      """
      Continuously prompt the user for input, interact with the OpenAI API, and handle the conversation flow.

      """
      try:
          while True:
              prompt = input("\n\nYour request: ")
              if prompt.lower() == 'exit':
                  break
              else:

                self.message = None
                self.runThread = None
                self.s_results = None
                self.u_request = None

                # Display User Prompt
                print(f"User Prompt: {prompt}\n")

                # Create a new user request message in the main thread
                self.create_message_thread(role="user", content=prompt)

                # Create a new thread run in the main thread
                self.create_thread_run()

                # Wait for the thread to finish
                run = self.wait_for_run_completion()

                # Retrieve the incomplete run message
                # run = self.retrieve_thread_run(run_id="run_BLIBQuy1sBYSXT2GxelyoBhv")

                # Wait for the thread to ask for action to be performed
                while run and run.status == 'requires_action':
                    run = self.submit_tool_outputs(run)
                    print(f"Run Status: {run.status}\n")
                    if run is not None:
                        run = self.wait_for_run_completion()
                    else:
                        print("Required Action Was not performed well")
                        break
                    time.sleep(1)

                # Check if run status is failed then continue it
                if run and run.status == 'failed':
                  print(run)
                  continue
              self.print_messages_from_thread()
      except Exception as error:
          # Handle any exceptions that occur during the conversation
          print(f"Encountered exception in ask to user prompt:: {error}")

# Code Execution is start from this point entry point
if __name__ == "__main__":
  # Load environment variables
  load_dotenv()
  assistantName="Open AI Bing Search Assistant"
  assistantInstructions="You are a real estate expert specializing in rentals. Call function 'perform_bing_search' when provided a user query. Call function 'process_search_results' when you receive the search results."
  assistantToolsArray=[
    {"type": "code_interpreter"},
    {
      "type": "function",
      "function": {
        "name": "perform_bing_search", # Function itself should run a GPT OpenAI-query that asks the OpenAI to generate (and return) a Bing-search-query.
        "description": "Determine a Bing search query from the user_request for specified information and execute the search",
        "parameters": {
          "type": "object",
          "properties": {
            "user_request": {"type": "string", "description": "The user's request, used to formulate a Bing search message"},
          },
          "required": ["user_request"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "process_search_results", # Function itself should send the Bing seardh results to openai to assess the results, and then return the results of that assessment to the user.
        "description": "Analyze Bing search results and return a summary of the results that most effectively answer the user's request",
        "parameters": {
          "type": "object",
          "properties": {
            "search_results": {"type": "string", "description": "The results from the Bing search to analyze"},
          },
          "required": ["search_results"]
        }
      }
    }
  ]

  # initialize the OpenAIBingSearchAssistant with required parameters example: assistantName, assistantInstructions, assistantToolsArray
  objectOpenAIBingSearchAssistant = OpenAIBingSearchAssistant()

  user_response = input("Do you want to use existing assistant if yes then please enter your assistant id othewise enter no to create a new assistant!: ")
  if user_response.lower() == "no":
    # Create New Assistant with required parameters example: assistantName, assistantInstructions, assistantToolsArray
    objectOpenAIBingSearchAssistant.create_assistant(assistantName,assistantInstructions,assistantToolsArray)
  else:
    # Or Retreive Existing Assistant By Id example: assistantId=asst_7OHuOKBNZw5uU2HvuCfcvyFH
    objectOpenAIBingSearchAssistant.retrieve_assistant(assistantId=user_response)

  user_response = input("Do you want to use existing main thread if yes then please enter your main thread id othewise enter no to create a new thread!: ")
  if user_response.lower() == "no":
    # Create New Main Thread with required parameters
    objectOpenAIBingSearchAssistant.create_main_thread()
  else:
    # Or Retreive Existing Main Thread By Id example: mainThreadId=threw_7OHuOKBNZw5uU2HvuCfcvyFH
    objectOpenAIBingSearchAssistant.retrieve_main_thread(assismainThreadIdtantId=user_response)

  # Display All Ids
  print("Assistant Id:"+objectOpenAIBingSearchAssistant.assistant.id)
  print("MainThread Id:"+objectOpenAIBingSearchAssistant.mainThread.id)
  # Start Ongoing conversation Loop
  objectOpenAIBingSearchAssistant.ask_to_user_promt()

  time.sleep(1)
