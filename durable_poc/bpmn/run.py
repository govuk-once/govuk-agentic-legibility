from SpiffWorkflow.bpmn.parser.BpmnParser import BpmnParser
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow


BPMN_FILE = "change_of_address.bpmn"
PROCESS_ID = "change_address"
USER_TASK = 16
SERVICE_TASK = 32

def main():
    # Load BPMN
    parser = BpmnParser()
    parser.add_bpmn_files([BPMN_FILE])

    spec = parser.get_spec(PROCESS_ID)

    # Create workflow instance
    workflow = BpmnWorkflow(spec)

    # Execute automatic engine work
    workflow.do_engine_steps()

    print("\nStarting Change of Address workflow")

    while not workflow.is_completed():

        ready_tasks = [
            t for t in workflow.get_tasks()
            if t.state in (USER_TASK, SERVICE_TASK)
        ]

        task = ready_tasks[0] if ready_tasks else None

        if task is None:
            print("\nNo ready task found.")
            print("\nCurrent task states:")

            for t in workflow.get_tasks():
                print(
                    t.task_spec.name,
                    t.task_spec.__class__.__name__,
                    t.state,
                )

            break

        task_name = task.task_spec.name

        print(f"\n=== {task_name} ===")
        print("Task ID:", task.id)
        print("Task Name:", task.task_spec.name)
        print("Task Type:", task.task_spec.__class__.__name__)
        print("Task State:", task.state)
        print()

        # User task handlers
        if task_name == "provide_details":

            name = input("Name: ")
            postcode = input("Postcode: ")

            task.set_data(
                name=name,
                postcode=postcode,
            )

        elif task_name == "upload_id":

            print("Identity evidence uploaded")

            task.set_data(
                identity_verified=True
            )

        elif task_name == "review":

            approved = (
                input("Approve application? (y/n): ")
                .strip()
                .lower() == "y"
            )

            task.set_data(
                approved=approved
            )

        elif task_name == "update_address":

            print(
                "Updating driving licence address..."
            )

        elif task_name == "reject":

            print(
                "Rejecting application..."
            )

        # Complete current task
        print()
        print("Task data:", task.data)
        
        task.complete()

        # Move workflow forward
        workflow.do_engine_steps()

    print("\nWorkflow completed successfully")


if __name__ == "__main__":
    main()