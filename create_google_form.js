/**
 * 🚜 Agri Solutions Group - Automated Google Form Generator
 * 
 * Instructions:
 * 1. Go to https://script.google.com/home/start
 * 2. Click "New project" (+).
 * 3. Delete any default text, paste this entire script, and click "Run" (▶️).
 * 4. Your complete Google Form is instantly created in your Google Drive!
 */

function createAgriStaffForm() {
  var form = FormApp.create('🚜 Agri Solutions Group — Junior Moderator Application (FS25)');
  
  form.setDescription(
    'Thank you for your interest in joining our staff team! As a Junior Moderator, you will assist in managing our Discord community and our dedicated Farming Simulator 25 multiplayer servers.\n\n' +
    '📌 Minimum Requirements:\n' +
    '• Must be at least 15 years of age (maturity exceptions considered).\n' +
    '• Clear, working microphone for voice communications.\n' +
    '• Owns a legitimate copy of Farming Simulator 25.\n' +
    '• Available at least 4 to 6 hours per week.'
  );

  // -------------------------------------------------------------
  // PART 1: GENERAL INFORMATION & AVAILABILITY
  // -------------------------------------------------------------
  form.addSectionHeaderItem().setTitle('PART 1: General Information & Availability');

  form.addTextItem()
    .setTitle('1. What is your full name or preferred nickname?')
    .setRequired(true);

  form.addTextItem()
    .setTitle('2. What is your Discord username (including display name)?')
    .setRequired(true);

  form.addTextItem()
    .setTitle('3. What is your age and date of birth?')
    .setRequired(true);

  form.addTextItem()
    .setTitle('4. What is your time zone / country of residence?')
    .setRequired(true);

  var hoursItem = form.addMultipleChoiceItem();
  hoursItem.setTitle('5. How many hours per week can you actively dedicate to moderating?')
    .setChoices([
      hoursItem.createChoice('3 – 5 hours per week'),
      hoursItem.createChoice('5 – 10 hours per week'),
      hoursItem.createChoice('10 – 15 hours per week'),
      hoursItem.createChoice('15+ hours per week')
    ])
    .setRequired(true);

  var activeItem = form.addCheckboxItem();
  activeItem.setTitle('6. Which times of the week are you most active?')
    .setChoices([
      activeItem.createChoice('Weekdays (Daytime)'),
      activeItem.createChoice('Weekdays (Evening / Night)'),
      activeItem.createChoice('Weekends (Daytime)'),
      activeItem.createChoice('Weekends (Evening / Night)')
    ])
    .setRequired(true);

  // -------------------------------------------------------------
  // PART 2: MOTIVATION & BACKGROUND
  // -------------------------------------------------------------
  form.addSectionHeaderItem().setTitle('PART 2: Motivation & Background');

  form.addParagraphTextItem()
    .setTitle('7. Why do you want to become a Junior Moderator for Agri Solutions Group?')
    .setHelpText('Please provide at least 3 detailed sentences explaining your motivation.')
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('8. Do you have previous staff or moderation experience in other Discord servers or gaming communities?')
    .setHelpText('If yes, please briefly describe the server, your role, and key responsibilities.')
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('9. What do you consider your 2 greatest strengths and 2 areas for personal improvement?')
    .setRequired(true);

  // -------------------------------------------------------------
  // PART 3: FARMING SIMULATOR 25 & GAMEPLAY KNOWLEDGE
  // -------------------------------------------------------------
  form.addSectionHeaderItem().setTitle('PART 3: Farming Simulator 25 & Gameplay Knowledge');

  form.addTextItem()
    .setTitle('10. How long have you been playing the Farming Simulator franchise (FS19 / FS22 / FS25)?')
    .setRequired(true);

  form.addTextItem()
    .setTitle('11. What is your favorite branch of agriculture or primary role in FS25?')
    .setHelpText('e.g., Arable crop harvesting, Contracting/Loonwerk, Livestock & Dairy, Forestry, or Farm Logistics.')
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('12. How would you guide a player who is encountering mod conflicts, game crashes, or sync errors when connecting to the FS25 dedicated server?')
    .setRequired(true);

  // -------------------------------------------------------------
  // PART 4: PRACTICAL SCENARIOS (CASE STUDIES)
  // -------------------------------------------------------------
  form.addSectionHeaderItem().setTitle('PART 4: Practical Scenarios (Case Studies)');

  form.addParagraphTextItem()
    .setTitle('🌾 Scenario A: Toxic Argument in General Discord Chat')
    .setHelpText('Two members enter a heated public argument in the main chat over a failed contracting job on the FS25 server with personal insults. What is your immediate step, and what do you do if they continue after your warning?')
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('🚜 Scenario B: Griefing & Trolling on the Dedicated Server')
    .setHelpText('A player joins the FS25 server, plows over another farm\'s harvested fields without permission, and drives a combine harvester into a deep lake. What immediate in-game and Discord actions do you take, and what evidence do you collect?')
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('📢 Scenario C: Unsolicited Advertising via DM or Chat')
    .setHelpText('A member posts invite links to their competing FS25 server in public chat and sends direct messages (DMs) to active players. What moderation action do you take?')
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('🤝 Scenario D: A Personal Friend Violates Server Rules')
    .setHelpText('A close in-game friend repeatedly violates the farm machinery rules expecting you to shield them. How do you maintain neutrality professionally?')
    .setRequired(true);

  // -------------------------------------------------------------
  // PART 5: ACKNOWLEDGMENT & CONFIRMATION
  // -------------------------------------------------------------
  form.addSectionHeaderItem().setTitle('PART 5: Acknowledgment & Confirmation');

  var confirmItem = form.addCheckboxItem();
  confirmItem.setTitle('Please check all boxes to confirm:')
    .setChoices([
      confirmItem.createChoice('I confirm that all information provided in this application is accurate, truthful, and written by myself.'),
      confirmItem.createChoice('I understand that submitting an application does not guarantee acceptance and that Management holds the final decision.'),
      confirmItem.createChoice('I agree to maintain complete confidentiality regarding all internal staff discussions and private staff channels.')
    ])
    .setRequired(true);

  Logger.log('🎉 Form Created Successfully!');
  Logger.log('Edit URL: ' + form.getEditUrl());
  Logger.log('Share Link for Players: ' + form.getPublishedUrl());
}
