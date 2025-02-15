<html>
<h1>Personal Finance Application</h1>
<table>
    <tr>
        <th>Last Updated On</th>
        <th>Update Description</th>
    </tr>
    <tr>
        <td>01/15/2023</td>
        <td>Created README and Dashboard with Expenses</td>
    </tr>
    <tr>
        <td>10/15/2024</td>
        <td>Created Streamlit app with features like transaction import, transaction cleaner, transaction editor and Dashboard to visualize breakdown of transactions by Account Type and Category</td>
    </tr>
    <tr>
        <td>02/15/2025</td>
        <td>Pushed code changes with parameters saved in config.json</td>
    </tr>
</table>

<h1>Objective:</h1>
<p>This app allows users to import transactions from multiple accounts, have them consolidated, allow for transaction categorization and finally visualize the breakdown of transactions by Account Type and Category.</p>

<h1>Features of this Application include:</h1>
<ol>
    <li><strong>Import Transactions:</strong> This tab allows users to select a specific Account and upload a file to record transactions under that account.</li>
    <li><strong>Transaction Cleaner:</strong> This tab allows users to consolidate all transactions into a single dataset for further transformations and analysis.</li>
    <li><strong>Transaction Editor:</strong> This tab allows users to update Category values for individual transactions and save the changes made to the transaction category. It also allows users to bring in new transactions and take a backup of the updated dataset.</li>
    <li><strong>Dashboard:</strong> Allows users to visualize the breakdown of transactions by Account Type or Category. It also provides a tabular view of the aggregated dataset and the entire dataset with all transaction details used in the aggregation.</li>
</ol>

<h1>Next Steps:</h1>
<ul>
    <li> [x] Add a reference dataset to capture Category for Description, Account Type, and Amount combination to apply it to new transactions.</li>
    <li> [x] Update the Transaction_Editor class to include an option to auto-populate Categories for records without Category values. Utilize Supervised Learning and Classification techniques to classify Transactions into specific categories.</li>
    <li> [x] Apply data consistency checks on File Imports and throw exceptions when the newly uploaded dataset does not match the table structure of the existing dataset.</li>
    <li> [ ] Host the application on a private server</li>
    <li> [ ] Organize the visualizations in Dashboard for better user experience</li>
</ul>
</html>