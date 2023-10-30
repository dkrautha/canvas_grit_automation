# `.env` File Configuration

You'll need the following variables in your `.env` file:

- CANVAS_API_URL="https://sit.instructure.com"
  - Your Canvas URL
- CANVAS_API_KEY=""
  - Your Canvas API Key
  - Currently being used with a key that has instructor level access, we haven't tested how little access you can actually have.
- CANVAS_COURSE_ID="70076"
  - Your Canvas Course ID
- CANVAS_QUIZ_IDS="pg:Laser Cutter=440133,pg:Band Saw=438799,pg:Drill Press=438798"
  - A comma separated list of permission groups and their quiz IDs
  - For example, "pg:Laser Cutter=440133"
- GRIT_URL=""
  - Your Grit URL
- GRIT_API_KEY=""
  - Your Grit API Key
- LOG_FILE="grit.log"
  - File location to store log information
- UPLOAD_TO_GRIT=false
  - Whether to actually do the upload to grit, mainly for debugging
- BACKUP_FOLDER="/home/davidk/Projects/machine_shop/uploads"
  - The folder to store backups in
  - Populated when the export server is hit at it's endpoint
